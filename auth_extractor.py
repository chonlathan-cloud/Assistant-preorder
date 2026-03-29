"""
Lazada Session Extractor
========================
Opens a Chromium browser (non-headless) for manual Lazada login.
After login, click the on-screen "💾 Save Session" button to export
cookies + localStorage into session_acc_1.json.

Uses playwright-stealth to avoid bot detection.

Usage:
    python auth_extractor.py                     # default: session_acc_1.json
    python auth_extractor.py --account 2         # saves as session_acc_2.json
    python auth_extractor.py --output my.json    # custom output filename
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth


# ─── Constants ────────────────────────────────────────────────────────────────
LAZADA_LOGIN_URL = "https://member.lazada.co.th/user/login"
LAZADA_HOME_URL  = "https://www.lazada.co.th"
OUTPUT_DIR       = Path(__file__).parent / "sessions"

# Selectors / indicators that the user has logged in
LOGGED_IN_INDICATORS = [
    '[class*="MyAccount"]',
    '[class*="myaccount"]',
    'a[href*="/user/"]',
    '[data-mod-name="member"]',
]


async def inject_save_button(page: Page) -> None:
    """Inject a floating 'Save Session' button into the page."""
    await page.evaluate("""
    () => {
        if (document.getElementById('__save_session_btn')) return;

        const btn = document.createElement('button');
        btn.id = '__save_session_btn';
        btn.innerText = '💾  Save Session';
        btn.style.cssText = `
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999999;
            padding: 14px 28px;
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(135deg, #f85032, #e73827);
            border: none;
            border-radius: 12px;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(232, 56, 39, 0.45);
            transition: all 0.2s ease;
            font-family: 'Segoe UI', sans-serif;
        `;
        btn.onmouseover = () => {
            btn.style.transform = 'scale(1.05)';
            btn.style.boxShadow = '0 8px 28px rgba(232, 56, 39, 0.6)';
        };
        btn.onmouseout = () => {
            btn.style.transform = 'scale(1)';
            btn.style.boxShadow = '0 6px 20px rgba(232, 56, 39, 0.45)';
        };
        btn.onclick = () => {
            window.__SESSION_SAVE_CLICKED = true;
            btn.innerText = '✅  Saving…';
            btn.style.background = 'linear-gradient(135deg, #38b249, #2d8f3c)';
            btn.style.pointerEvents = 'none';
        };
        document.body.appendChild(btn);
    }
    """)


async def inject_status_banner(page: Page, message: str, color: str = "#38b249") -> None:
    """Show a top-of-page status banner."""
    # Escape single quotes to avoid breaking JS string literals
    safe_message = message.replace("'", "\\'")
    safe_color = color.replace("'", "\\'")
    await page.evaluate(f"""
    () => {{
        let banner = document.getElementById('__session_banner');
        if (!banner) {{
            banner = document.createElement('div');
            banner.id = '__session_banner';
            banner.style.cssText = `
                position: fixed;
                top: 0; left: 0; right: 0;
                z-index: 999999;
                padding: 12px;
                text-align: center;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI', sans-serif;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(banner);
        }}
        banner.style.background = '{safe_color}';
        banner.style.color = '#fff';
        banner.innerText = '{safe_message}';
    }}
    """)


async def wait_for_save_click(page: Page, timeout_minutes: int = 15) -> bool:
    """Wait for the user to click the Save Session button."""
    deadline = asyncio.get_event_loop().time() + (timeout_minutes * 60)

    while asyncio.get_event_loop().time() < deadline:
        try:
            clicked = await page.evaluate("() => window.__SESSION_SAVE_CLICKED === true")
            if clicked:
                return True
        except Exception:
            pass  # page might have navigated
        await asyncio.sleep(0.5)

    return False


async def extract_local_storage(page: Page) -> dict:
    """Extract all localStorage key-value pairs from the current page."""
    try:
        return await page.evaluate("""
        () => {
            const data = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                data[key] = localStorage.getItem(key);
            }
            return data;
        }
        """)
    except Exception:
        return {}


async def save_session(context: BrowserContext, page: Page, output_path: Path) -> None:
    """Save browser context state + localStorage to JSON."""
    # 1) Playwright storage state (cookies + sessionStorage + localStorage origins)
    state = await context.storage_state()

    # 2) Extra: grab full localStorage from current Lazada page
    local_storage_data = await extract_local_storage(page)

    # 3) Merge into a single output
    session_data = {
        "storage_state": state,
        "lazada_local_storage": local_storage_data,
        "extracted_from": page.url,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(session_data, indent=2, ensure_ascii=False), encoding="utf-8")


async def run(account: int, output: str | None) -> None:
    """Main extraction flow."""
    # Resolve output path
    if output:
        out_path = Path(output)
    else:
        out_path = OUTPUT_DIR / f"session_acc_{account}.json"

    print(f"\n{'='*60}")
    print(f"  🔐  Lazada Session Extractor")
    print(f"  📦  Output → {out_path}")
    print(f"{'='*60}\n")

    stealth = Stealth(
        navigator_languages_override=("th-TH", "th"),
        navigator_platform_override="MacIntel",
    )

    async with stealth.use_async(async_playwright()) as p:
        # Launch Chromium in headed mode (non-headless)
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
            timezone_id="Asia/Bangkok",
        )

        page = await context.new_page()

        # Navigate to Lazada login
        print("🌐  Opening Lazada login page…")
        await page.goto(LAZADA_LOGIN_URL, wait_until="domcontentloaded")

        # Show instruction banner
        await inject_status_banner(
            page,
            "🔑  กรุณาเข้าสู่ระบบ Lazada แล้วกดปุ่ม 'Save Session' ด้านล่างขวา",
            "#e73827",
        )
        await inject_save_button(page)

        # Re-inject button on every navigation (Lazada SPA transitions)
        async def _on_load(p: Page) -> None:
            try:
                await inject_save_button(p)
                # Check if still not saved
                clicked = await p.evaluate("() => window.__SESSION_SAVE_CLICKED === true")
                if not clicked:
                    await inject_status_banner(
                        p,
                        "✅  ล็อกอินสำเร็จ! กดปุ่ม 'Save Session' เพื่อบันทึก Session",
                        "#38b249",
                    )
            except Exception:
                pass

        page.on("load", lambda p: asyncio.ensure_future(_on_load(p)))

        print("⏳  Waiting for you to log in and click 'Save Session'…")
        print("    (Timeout: 15 minutes)\n")

        # Wait for user to click Save
        saved = await wait_for_save_click(page, timeout_minutes=15)

        if saved:
            await inject_status_banner(page, "💾  กำลังบันทึก Session…", "#2196F3")
            await asyncio.sleep(1)

            await save_session(context, page, out_path)

            await inject_status_banner(page, "✅  บันทึก Session สำเร็จ! ปิด Browser ได้เลย", "#38b249")
            print(f"✅  Session saved → {out_path}")
            print(f"    File size: {out_path.stat().st_size:,} bytes")
            await asyncio.sleep(3)
        else:
            print("⚠️  Timeout — no session saved.")

        await browser.close()

    print("\n🏁  Done.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lazada Session Extractor — extract cookies & localStorage for the shopping bot",
    )
    parser.add_argument(
        "--account",
        type=int,
        default=1,
        help="Account number (default: 1). Determines output filename: session_acc_{N}.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output file path (overrides --account naming)",
    )
    args = parser.parse_args()

    asyncio.run(run(account=args.account, output=args.output))


if __name__ == "__main__":
    main()
