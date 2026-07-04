"""
Generate bookend background art for the hackathon demo video via Vertex AI
Imagen, using the same ADC auth the rest of the backend already uses.

Usage:
    python backend/scripts/gen_video_assets.py
"""

from __future__ import annotations

import os
from pathlib import Path

for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_k, None)

PROJECT = os.environ.get("VERTEXAI_PROJECT", "ai-negotiation-copilot")
LOCATION = os.environ.get("VERTEXAI_LOCATION", "us-central1")
OUT_DIR = Path(__file__).resolve().parents[2] / "video" / "hf" / "assets"

PROMPTS = {
    "bg_coldopen.png": (
        "Abstract dark technical background, near-black navy base, "
        "a faint glowing temporal knowledge graph of nodes and edges drifting "
        "across the frame, thin glowing cyan connection lines, a few "
        "nodes glowing soft magenta, sparse and elegant not dense, "
        "large empty negative space in the center-left for text overlay, "
        "subtle film grain, absolutely no text, no letters, no numbers, no "
        "words, no labels, no logos anywhere in the image, wide 16:9 cinematic "
        "composition, medical data visualization aesthetic, high detail, dark "
        "moody lighting"
    ),
}


def main() -> None:
    from google import genai
    from google.genai import types

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    for filename, prompt in PROMPTS.items():
        print(f"generating {filename} ...")
        resp = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="DONT_ALLOW",
            ),
        )
        img = resp.generated_images[0].image
        out_path = OUT_DIR / filename
        out_path.write_bytes(img.image_bytes)
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
