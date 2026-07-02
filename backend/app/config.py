"""
Central config + Cognee/Vertex wiring. Import this FIRST, before any other
Cognee usage, so env + provider are set before Cognee builds its engines.

Auth model: Vertex AI via Application Default Credentials (ADC). NO API key.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- 1. Strip anything that would hijack Vertex ADC auth -------------------
#     If GEMINI_API_KEY / GOOGLE_API_KEY exist, LiteLLM/google-genai use them
#     instead of ADC and fail. Remove them for this process.
for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_k, None)

# --- 2. GCP / Vertex ------------------------------------------------------
PROJECT = os.environ.setdefault("VERTEXAI_PROJECT", "ai-negotiation-copilot")
LOCATION = os.environ.setdefault("VERTEXAI_LOCATION", "us-central1")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT)

EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gemini-2.5-flash")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")

# --- 3. Embeddings: local & free (CPU) ------------------------------------
os.environ.setdefault("EMBEDDING_PROVIDER", "fastembed")
os.environ.setdefault("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "384")

# Import cognee AFTER env is set.
import cognee  # noqa: E402

# --- 4. Windows MAX_PATH fix: keep Cognee storage on a SHORT root ----------
_SYS_DIR = os.environ.get("COGNEE_SYS_DIR", r"C:\cg\sys")
_DATA_DIR = os.environ.get("COGNEE_DATA_DIR", r"C:\cg\data")
os.makedirs(_SYS_DIR, exist_ok=True)
os.makedirs(_DATA_DIR, exist_ok=True)
cognee.config.system_root_directory(_SYS_DIR)
cognee.config.data_root_directory(_DATA_DIR)

# --- 5. Route Cognee's LLM through Vertex (no API key) ---------------------
#     'custom' + vertex_ai/<model> tells LiteLLM to use Vertex; project/location
#     come from the VERTEXAI_* env vars; credentials come from ADC.
cognee.config.set_llm_provider("custom")
cognee.config.set_llm_model(f"vertex_ai/{EXTRACTION_MODEL}")
# NOTE: api_key intentionally NOT set — Vertex uses ADC.
# If a Cognee version requires a non-empty key, set LLM_API_KEY=vertex-adc in .env.
if os.environ.get("LLM_API_KEY"):
    cognee.config.set_llm_api_key(os.environ["LLM_API_KEY"])


def summary() -> str:
    return (
        f"Provider=custom  Model=vertex_ai/{EXTRACTION_MODEL}  "
        f"Project={PROJECT}  Region={LOCATION}  Embeddings=fastembed(local)"
    )
