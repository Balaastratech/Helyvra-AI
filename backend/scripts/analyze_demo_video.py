"""
Send the rendered hackathon demo video to Gemini (Vertex AI) for a timestamped
visual+audio analysis, using the same ADC auth the rest of the backend already
uses (no API key). Uploads to GCS first since Vertex needs a file_uri for
anything past the small inline-bytes limit (the video is ~100MB).

Usage:
    python backend/scripts/analyze_demo_video.py
    python backend/scripts/analyze_demo_video.py --video video/out/total-recall-demo.mp4 --bucket gs://balaastra-content/video-review
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Same ADC hijack-prevention as app/config.py, without importing Cognee.
for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_k, None)

PROJECT = os.environ.get("VERTEXAI_PROJECT", "ai-negotiation-copilot")
LOCATION = os.environ.get("VERTEXAI_LOCATION", "us-central1")
MODEL = os.environ.get("VIDEO_ANALYSIS_MODEL", "gemini-2.5-pro")

PROMPT = """You are analyzing a ~2-minute hackathon demo video for "Total Recall" (a
self-healing, time-aware clinical memory system built on Cognee). I need a precise,
timestamped report of the video so a reviewer who has NOT watched it can judge it
accurately.

Go through the video in chronological order and produce the following:

## 1. Scene-by-scene breakdown
For EVERY distinct scene/shot change, give:
- Timestamp range (e.g. 0:00-0:12)
- WHAT IS SHOWN on screen (UI elements, text on screen, colors, any visual effect,
  what the cursor/interaction does)
- WHAT IS SAID (verbatim or near-verbatim voiceover/narration text for that range)
- SYNC CHECK: does the narration match what's on screen at that exact moment, or is
  there a lag/mismatch (e.g. narrator describes something before/after it appears)?
- Any on-screen captions/subtitles and whether they match the spoken audio exactly

## 2. Pacing and clarity issues
Flag anything that could confuse or lose a judge who is watching once, at normal speed:
- Text on screen that's too small, too fast, or on screen too briefly to read
- Any dead air, awkward pause, or moment where nothing new happens for 2+ seconds
- Any jump cut that skips context a first-time viewer would need
- Audio issues: unclear TTS pronunciation, volume inconsistency, pacing too fast/slow
- Whether the total video length is under 2 minutes (state exact runtime)

## 3. Hook and structure check
- What is shown/said in the FIRST 15 seconds? Does it immediately state the problem
  and the product's answer, or does it warm up slowly first?
- Is there a clear "before vs after" or "naive vs smart" contrast moment? If yes,
  timestamp it and quote the exact before/after lines shown or said.
- Is there a clear ending / call-to-action / summary in the last 10 seconds?

## 4. Technical credibility signals
List every moment the video shows or names a SPECIFIC technology, API, or concept
(e.g. "Cognee", "temporal search", "knowledge graph", "self-healing", "LangGraph",
a function name, a search type). For each, note the exact timestamp and exact wording
used, so I can check it against the actual codebase for accuracy.

## 5. Full verbatim transcript
Provide a plain, full transcript of every spoken word in order, with timestamps every
~10 seconds, so I can read the narration alone without watching.

## 6. Your own critique (separate section, clearly labeled "GEMINI CRITIQUE")
Given this is being judged on: Potential Impact, Creativity & Innovation, Technical
Excellence, Best Use of Cognee (specifically remember/recall/improve/forget lifecycle
API usage), User Experience, and Presentation Quality -- call out anything in the video
that undersells, confuses, or fails to demonstrate any of these six areas, even if it's
a small detail. Be blunt and specific with timestamps, not general.

Format the entire output in markdown with clear headers so it can be pasted into
another tool for further review."""


def upload_to_gcs(video_path: Path, bucket_prefix: str) -> str:
    dest = f"{bucket_prefix.rstrip('/')}/{video_path.name}"
    print(f"Uploading {video_path} -> {dest} ...")
    gcloud = "gcloud.cmd" if os.name == "nt" else "gcloud"
    subprocess.run(
        [gcloud, "storage", "cp", str(video_path), dest],
        check=True,
        shell=(os.name == "nt"),
    )
    return dest


def analyze(gcs_uri: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4"),
                    types.Part.from_text(text=PROMPT),
                ],
            )
        ],
        config=types.GenerateContentConfig(temperature=0),
    )
    return response.text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="video/out/total-recall-demo.mp4")
    parser.add_argument("--bucket", default="gs://balaastra-content/video-review")
    parser.add_argument("--out", default="docs/VIDEO_ANALYSIS_REPORT.md")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        sys.exit(f"Video not found: {video_path}")

    gcs_uri = upload_to_gcs(video_path, args.bucket)
    print(f"Analyzing with {MODEL} via Vertex AI (project={PROJECT}, location={LOCATION}) ...")
    report = analyze(gcs_uri)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
