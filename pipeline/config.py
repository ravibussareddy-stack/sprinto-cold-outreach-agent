"""All tunable settings in one place. Values come from .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# OFFLINE=1 -> cached pages + canned model replies + local contacts CSV. No network, no keys.
OFFLINE = os.getenv("OFFLINE", "1") == "1"
# DRY_RUN=1 -> write emails to outbox/ instead of sending through Gmail.
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")          # gemini | anthropic
# Several free-tier keys are rotated: GEMINI_API_KEY1..3, or a single GEMINI_API_KEY.
GEMINI_API_KEYS = list(dict.fromkeys(
    k for k in (os.getenv(n, "").strip() for n in
                ["GEMINI_API_KEY1", "GEMINI_API_KEY2", "GEMINI_API_KEY3", "GEMINI_API_KEY"]) if k))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# Step 4: contact lookup
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
CONTACTS_CSV = ROOT / "data" / "contacts.csv"                # Apollo fallback (Option B)

# Step 7: Gmail. Case rule: the To: address is hardcoded to your own inbox.
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
TO_ADDRESS = os.getenv("TO_ADDRESS", "")       # set in .env: your own inbox
SENDER_NAME = os.getenv("SENDER_NAME", "Ravi")

# Step 3: qualification
QUALIFY_THRESHOLD = 70      # out of 100
MAX_AGENT_ROUNDS = 3        # extra pages the qualifier may fetch per company

PAGES_DIR = ROOT / "fixtures" / "pages"
CANNED_LLM = ROOT / "fixtures" / "llm_responses.json"
CACHE_DIR = ROOT / ".cache"
RUNS_DIR = ROOT / "runs"
OUTBOX_DIR = ROOT / "outbox"
