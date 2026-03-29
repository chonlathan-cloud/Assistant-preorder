"""
Sniper Worker — Visual Intelligence (Gemini Vision)
=====================================================
Uses Vertex AI (Gemini 1.5 Flash) as a fallback when Playwright
DOM selectors fail (UI changes, A/B tests, or pop-ups).
"""

import json
import logging
import re
from typing import Tuple, Optional

import vertexai
from vertexai.generative_models import GenerativeModel, Part

from worker.config import worker_settings

logger = logging.getLogger(__name__)

_initialized = False
_model: GenerativeModel | None = None


def _init_vertexai():
    global _initialized, _model
    if not _initialized:
        vertexai.init(
            project=worker_settings.GCP_PROJECT_ID,
            location=worker_settings.VERTEX_AI_LOCATION,
        )
        # Using 1.5-flash as the optimal model for low-latency visual spatial understanding
        _model = GenerativeModel(worker_settings.GEMINI_MODEL)
        _initialized = True


def find_element_on_screen(
    screenshot_bytes: bytes,
    label_to_find: str,
    viewport_width: int = 1366,
    viewport_height: int = 768,
) -> Tuple[Optional[Tuple[int, int]], str]:
    """
    Send a screenshot to Gemini Vision and ask for the coordinates of a specific element.

    Returns:
      - (x, y) pixel coordinates to click, or None if not found.
      - A log message describing what happened.
    """
    _init_vertexai()

    prompt = f"""
    You are an intelligent visual web automation agent.
    Task: Find the exact location of the "{label_to_find}".
    
    If you find it, return its bounding box coordinates.
    The response MUST be ONLY a JSON array of exactly four integers representing the normalized 
    bounding box [ymin, xmin, ymax, xmax] scaled to 1000. Example: [450, 200, 500, 350].
    
    If the element is absolutely not found, return "NOT_FOUND".
    """

    image_part = Part.from_data(data=screenshot_bytes, mime_type="image/png")

    try:
        response = _model.generate_content(
            [image_part, prompt],
            # Use lower temperature for more deterministic coordinate output
            generation_config={"temperature": 0.1, "max_output_tokens": 128},
        )
        
        reply = response.text.strip()
        
        if "NOT_FOUND" in reply:
            return None, f"AI could not find '{label_to_find}' on screen."

        # Extract the JSON array using regex in case model adds formatting (e.g., markdown ```json [1,2,3,4] ```)
        match = re.search(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", reply)
        if not match:
            return None, f"AI returned invalid format for '{label_to_find}': {reply}"

        ymin, xmin, ymax, xmax = map(int, match.groups())

        # Gemini 1.5 bounding boxes are normalized to 1000x1000
        # Calculate the center of the bounding box
        center_x_norm = (xmin + xmax) / 2.0 / 1000.0
        center_y_norm = (ymin + ymax) / 2.0 / 1000.0

        # Scale to viewport pixels
        px_x = int(center_x_norm * viewport_width)
        px_y = int(center_y_norm * viewport_height)

        return (px_x, px_y), f"AI found '{label_to_find}' at ({px_x}, {px_y}) [raw box: {ymin},{xmin},{ymax},{xmax}]"

    except Exception as e:
        logger.error(f"Gemini API error during visual fallback: {e}")
        return None, f"AI Vision failed with exception: {str(e)}"
