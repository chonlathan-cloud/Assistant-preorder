"""
Sniper Worker — Core Bot Logic
================================
Headless Playwright automation for Lazada purchasing.

Flow:
  1. Load session from GCS
  2. Navigate to product page
  3. Select variant(s) + set quantity
  4. Flash-sale poll (if Buy Now disabled)
  5. Checkout: Buy Now → Place Order
  6. Screenshot result + log to Firestore
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth import Stealth

from worker.config import worker_settings
from worker.schemas import ExecuteRequest, VariantItem
from worker.visual_intelligence import find_element_on_screen

logger = logging.getLogger(__name__)

# ─── Chromium Launch Args (optimized for Cloud Run) ──────────────────────────

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",       # Cloud Run has limited /dev/shm
    "--disable-gpu",                  # no GPU in Cloud Run
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-translate",
    "--disable-default-apps",
    "--no-first-run",
    "--no-sandbox",                   # required in Docker
    "--single-process",               # reduce memory in containers
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-size=1366,768",
    "--hide-scrollbars",
    "--mute-audio",
]


# ─── Lazada Selectors ────────────────────────────────────────────────────────
# These are best-effort selectors; Lazada's DOM changes frequently.
# The bot falls back to text-matching and aria labels when ID selectors fail.

SELECTORS = {
    # Variant buttons (Lazada uses sku-variable-name for variant groups)
    "variant_container": '[class*="sku-variable"], [class*="sku-prop"]',
    "variant_button": 'button, [role="button"], span[class*="sku-name"]',

    # Quantity
    "qty_input": 'input[type="text"][class*="qty"], input.next-input, input[class*="quantity"]',
    "qty_plus": 'button[class*="next-after"], button[aria-label="Increase"]',

    # Buy Now
    "buy_now": 'button[class*="buynow"], button:has-text("ซื้อสินค้า"), button:has-text("Buy Now")',
    "add_to_cart": 'button[class*="addtocart"], button:has-text("หยิบใส่ตะกร้า"), button:has-text("Add to Cart")',

    # Checkout page
    "place_order": 'button[class*="checkout-btn"], button:has-text("สั่งซื้อ"), button:has-text("Place Order")',
    "payment_bank": '[class*="payment-method"] :has-text("โอนเงิน"), :has-text("Bank Transfer")',
    "payment_qr": '[class*="payment-method"] :has-text("QR"), :has-text("PromptPay")',

    # Order success indicators
    "order_success": '[class*="order-success"], [class*="thankyou"], :has-text("ขอบคุณ"), :has-text("Thank you")',
}


class SniperResult:
    """Tracks results across the sniper run."""

    def __init__(self):
        self.orders_placed: int = 0
        self.screenshots: list[str] = []
        self.errors: list[str] = []
        self.status: str = "pending"
        self.ai_usage_count: int = 0
        self.ai_logs: list[str] = []

    @property
    def is_success(self) -> bool:
        return self.orders_placed > 0


async def _take_screenshot(page: Page, name: str) -> str:
    """Take a screenshot and return the file path."""
    ss_dir = Path(worker_settings.SCREENSHOT_DIR)
    ss_dir.mkdir(parents=True, exist_ok=True)
    path = ss_dir / f"{name}_{int(time.time())}.png"
    await page.screenshot(path=str(path), full_page=False)
    logger.info(f"📸 Screenshot → {path}")
    return str(path)


async def _load_local_storage(page: Page, local_storage: dict[str, str]) -> None:
    """Inject localStorage entries into the current page."""
    if not local_storage:
        return
    for key, value in local_storage.items():
        escaped_key = json.dumps(key)
        escaped_val = json.dumps(value)
        await page.evaluate(f"localStorage.setItem({escaped_key}, {escaped_val})")
    logger.info(f"Injected {len(local_storage)} localStorage entries")


async def _use_visual_fallback(page: Page, label: str, result: SniperResult) -> bool:
    """Takes a screenshot, asks Gemini to find the element, and clicks it if found."""
    logger.info(f"🧠 Asking Gemini Vision to find: '{label}'")
    try:
        ss_bytes = await page.screenshot()
        result.ai_usage_count += 1
        
        # Get coordinates from Gemini
        coords, log_msg = find_element_on_screen(
            screenshot_bytes=ss_bytes,
            label_to_find=label,
            viewport_width=1366,
            viewport_height=768,
        )
        
        result.ai_logs.append(log_msg)
        logger.info(f"🧠 Vision Result: {log_msg}")

        if coords:
            px_x, px_y = coords
            await page.mouse.click(px_x, px_y)
            logger.info(f"🧠 AI Fallback clicked ({px_x}, {px_y}) successfully")
            await page.wait_for_timeout(1000)
            return True
            
        return False
    except Exception as e:
        logger.error(f"❌ Visual fallback failed: {e}", exc_info=True)
        return False


async def _clear_overlays(page: Page, result: SniperResult) -> None:
    """Check for popups/overlays and use AI to dismiss them."""
    logger.info("🧠 Checking for overlays/pop-ups to clear...")
    await _use_visual_fallback(page, "Close button or X icon to dismiss pop-up", result)


# ─── Variant Selection ────────────────────────────────────────────────────────

async def _select_variant(page: Page, variant_name: str, result: SniperResult) -> bool:
    """
    Click the variant button matching the given name.
    Tries multiple strategies: exact text, partial text, contains.
    """
    logger.info(f"🎯 Selecting variant: {variant_name}")

    strategies = [
        # Strategy 1: Button/span with exact text
        f'button:has-text("{variant_name}"), span:has-text("{variant_name}")',
        # Strategy 2: Any element in variant container
        f'[class*="sku"] :has-text("{variant_name}")',
        # Strategy 3: Image alt text (some variants are image-based)
        f'img[alt*="{variant_name}"]',
        # Strategy 4: Title attribute
        f'[title*="{variant_name}"]',
    ]

    for i, selector in enumerate(strategies):
        try:
            element = page.locator(selector).first
            if await element.is_visible(timeout=2000):
                await element.click()
                logger.info(f"✅ Variant '{variant_name}' selected (strategy {i+1})")
                await page.wait_for_timeout(500)  # let UI update
                return True
        except Exception:
            continue

    # AI Fallback if all strategies fail
    logger.warning(f"⚠️ DOM locators failed for variant '{variant_name}'. Trying AI fallback...")
    if await _use_visual_fallback(page, f"Button or image labeled '{variant_name}'", result):
        return True

    logger.error(f"❌ Completely failed to find variant '{variant_name}'")
    return False


# ─── Quantity ──────────────────────────────────────────────────────────────────

async def _set_quantity(page: Page, qty: int) -> bool:
    """Set the quantity input to the desired value."""
    logger.info(f"🔢 Setting quantity: {qty}")

    try:
        # Try direct input first
        qty_input = page.locator(SELECTORS["qty_input"]).first
        if await qty_input.is_visible(timeout=3000):
            await qty_input.triple_click()  # select all
            await qty_input.fill(str(qty))
            logger.info(f"✅ Quantity set to {qty}")
            return True
    except Exception:
        pass

    # Fallback: click the + button (qty - 1) times
    try:
        plus_btn = page.locator(SELECTORS["qty_plus"]).first
        if await plus_btn.is_visible(timeout=2000):
            for _ in range(qty - 1):
                await plus_btn.click()
                await page.wait_for_timeout(100)
            logger.info(f"✅ Quantity set to {qty} via + button")
            return True
    except Exception:
        pass

    logger.warning(f"⚠️ Could not set quantity to {qty}")
    return False


# ─── Flash Sale Polling ───────────────────────────────────────────────────────

async def _wait_for_buy_now(page: Page) -> bool:
    """
    Fast-poll until the 'Buy Now' button becomes active.
    Used for flash sales where the button starts disabled.
    """
    poll_interval = worker_settings.FLASH_POLL_INTERVAL_MS
    timeout = worker_settings.FLASH_POLL_TIMEOUT_S
    deadline = time.time() + timeout
    attempt = 0

    logger.info(f"⏱️ Flash-sale polling (every {poll_interval}ms, timeout {timeout}s)")

    while time.time() < deadline:
        attempt += 1
        try:
            buy_now = page.locator(SELECTORS["buy_now"]).first
            is_visible = await buy_now.is_visible(timeout=500)
            if is_visible:
                is_disabled = await buy_now.is_disabled()
                if not is_disabled:
                    logger.info(f"🟢 Buy Now active after {attempt} polls!")
                    return True
        except Exception:
            pass

        # Refresh page periodically (every 10 polls) to get fresh state
        if attempt % 10 == 0:
            logger.info(f"🔄 Refreshing page (poll #{attempt})")
            await page.reload(wait_until="domcontentloaded")
            await page.wait_for_timeout(300)

        await page.wait_for_timeout(poll_interval)

    logger.warning(f"⏰ Flash-sale timeout after {attempt} polls ({timeout}s)")
    return False


# ─── Checkout Flow ─────────────────────────────────────────────────────────────

async def _click_buy_now(page: Page, result: SniperResult) -> bool:
    """Click the Buy Now button."""
    try:
        buy_now = page.locator(SELECTORS["buy_now"]).first
        if await buy_now.is_visible(timeout=3000):
            is_disabled = await buy_now.is_disabled()
            if is_disabled:
                logger.info("Buy Now is disabled — entering flash-sale poll")
                if not await _wait_for_buy_now(page):
                    return False

            await buy_now.click()
            logger.info("✅ Buy Now clicked")
            await page.wait_for_load_state("domcontentloaded")
            return True
    except Exception as e:
        logger.error(f"❌ DOM Buy Now click failed: {e}")

    # AI Fallback
    logger.warning("⚠️ DOM locators failed for Buy Now. Trying AI fallback...")
    if await _use_visual_fallback(page, "Buy Now button (usually orange/red) or ซื้อสินค้า", result):
        await page.wait_for_load_state("domcontentloaded")
        return True

    return False


async def _select_payment_method(page: Page) -> bool:
    """Select Bank Transfer or QR Code payment on checkout page."""
    # Try Bank Transfer first, then QR
    for label, selector in [
        ("Bank Transfer", SELECTORS["payment_bank"]),
        ("QR / PromptPay", SELECTORS["payment_qr"]),
    ]:
        try:
            element = page.locator(selector).first
            if await element.is_visible(timeout=3000):
                await element.click()
                logger.info(f"✅ Payment method: {label}")
                await page.wait_for_timeout(500)
                return True
        except Exception:
            continue

    logger.warning("⚠️ Could not select payment method — using default")
    return False  # Not fatal; user may have pre-set default


async def _place_order(page: Page, result: SniperResult) -> bool:
    """Click Place Order on checkout page."""
    try:
        place_btn = page.locator(SELECTORS["place_order"]).first
        if await place_btn.is_visible(timeout=5000):
            await place_btn.click()
            logger.info("✅ Place Order clicked")
            await page.wait_for_load_state("domcontentloaded")
            return True
    except Exception as e:
        logger.error(f"❌ DOM Place Order failed: {e}")

    # AI Fallback
    logger.warning("⚠️ DOM Place Order failed. Checking for obstacles or trying AI fallback...")
    await _clear_overlays(page, result)
    if await _use_visual_fallback(page, "Place Order button (usually orange) or สั่งซื้อ", result):
        await page.wait_for_load_state("domcontentloaded")
        return True

    return False


async def _check_order_success(page: Page) -> bool:
    """Check if the order was placed successfully."""
    try:
        success = page.locator(SELECTORS["order_success"]).first
        return await success.is_visible(timeout=5000)
    except Exception:
        return False


# ─── Main Sniper Flow ─────────────────────────────────────────────────────────

async def execute_snipe(
    request: ExecuteRequest,
    session_data: dict[str, Any],
) -> SniperResult:
    """
    Execute the full sniper flow:
      1. Launch browser with session
      2. Navigate to product
      3. For each variant: select → set qty → buy → checkout
      4. Screenshot & return results
    """
    result = SniperResult()

    stealth = Stealth(
        navigator_languages_override=("th-TH", "th"),
        navigator_platform_override="MacIntel",
    )

    async with stealth.use_async(async_playwright()) as p:
        # Launch headless Chromium
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=CHROMIUM_ARGS,
        )

        # Create context with stored session
        storage_state = session_data.get("storage_state", {})

        context: BrowserContext = await browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
            timezone_id="Asia/Bangkok",
        )

        page: Page = await context.new_page()

        # Inject localStorage if available
        lazada_ls = session_data.get("lazada_local_storage", {})

        try:
            # ── Step 1: Navigate to product ──
            logger.info(f"🌐 Navigating to: {request.product_url}")
            await page.goto(
                request.product_url,
                wait_until="domcontentloaded",
                timeout=worker_settings.PAGE_LOAD_TIMEOUT,
            )
            await _load_local_storage(page, lazada_ls)
            await page.wait_for_timeout(1000)  # let product page settle

            # ── Step 2: Process each variant ──
            for variant in request.variants:
                logger.info(f"\n{'─'*50}")
                logger.info(f"Processing variant: {variant.name} × {variant.qty}")
                logger.info(f"{'─'*50}")

                for attempt in range(1, worker_settings.MAX_RETRY + 1):
                    logger.info(f"Attempt {attempt}/{worker_settings.MAX_RETRY}")

                    try:
                        # Select variant
                        if not await _select_variant(page, variant.name, result):
                            result.errors.append(f"Variant not found: {variant.name}")
                            ss = await _take_screenshot(page, f"variant_fail_{variant.name}")
                            result.screenshots.append(ss)
                            continue

                        # Set quantity
                        await _set_quantity(page, variant.qty)

                        # Click Buy Now (with flash-sale polling)
                        if not await _click_buy_now(page, result):
                            result.errors.append(f"Buy Now failed for {variant.name}")
                            ss = await _take_screenshot(page, f"buynow_fail_{variant.name}")
                            result.screenshots.append(ss)
                            # Go back and retry
                            await page.goto(
                                request.product_url,
                                wait_until="domcontentloaded",
                                timeout=worker_settings.PAGE_LOAD_TIMEOUT,
                            )
                            await page.wait_for_timeout(1000)
                            continue

                        # Select payment
                        await _select_payment_method(page)

                        # Place Order
                        if await _place_order(page, result):
                            # Check success
                            if await _check_order_success(page):
                                result.orders_placed += 1
                                ss = await _take_screenshot(page, f"success_{variant.name}")
                                result.screenshots.append(ss)
                                logger.info(f"🎉 ORDER PLACED: {variant.name} × {variant.qty}")
                                break  # Move to next variant
                            else:
                                ss = await _take_screenshot(page, f"checkout_unknown_{variant.name}")
                                result.screenshots.append(ss)
                                # Might still have succeeded — check page content
                                page_text = await page.text_content("body") or ""
                                if any(kw in page_text for kw in ["ขอบคุณ", "Thank you", "สั่งซื้อสำเร็จ"]):
                                    result.orders_placed += 1
                                    logger.info(f"🎉 ORDER PLACED (text match): {variant.name}")
                                    break
                        else:
                            ss = await _take_screenshot(page, f"placeorder_fail_{variant.name}")
                            result.screenshots.append(ss)

                    except Exception as e:
                        logger.error(f"Error on attempt {attempt}: {e}", exc_info=True)
                        ss = await _take_screenshot(page, f"error_{variant.name}_{attempt}")
                        result.screenshots.append(ss)

                    # Navigate back for retry
                    try:
                        await page.goto(
                            request.product_url,
                            wait_until="domcontentloaded",
                            timeout=worker_settings.PAGE_LOAD_TIMEOUT,
                        )
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            result.errors.append(str(e))
            try:
                ss = await _take_screenshot(page, "fatal_error")
                result.screenshots.append(ss)
            except Exception:
                pass

        finally:
            await browser.close()

    # Determine final status
    if result.orders_placed == len(request.variants):
        result.status = "success"
    elif result.orders_placed > 0:
        result.status = "partial"
    else:
        result.status = "failed"

    return result
