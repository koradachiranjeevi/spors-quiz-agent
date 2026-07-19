import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# App directories
DATA_DIR = BASE_DIR / "data"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
LOGS_DIR = BASE_DIR / "logs"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure directories exist
for directory in [DATA_DIR, CHROMA_DB_DIR, LOGS_DIR, ASSETS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Configuration values loaded from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# LLM provider settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")

# Unified LLM Key resolution based on provider
LLM_API_KEY = ""
if LLM_PROVIDER == "groq":
    LLM_API_KEY = GROQ_API_KEY or os.getenv("LLM_API_KEY", "")
elif LLM_PROVIDER == "together":
    LLM_API_KEY = TOGETHER_API_KEY or os.getenv("LLM_API_KEY", "")
elif LLM_PROVIDER == "openai":
    LLM_API_KEY = OPENAI_API_KEY
else:
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
# Default model fallback based on provider
default_models = {
    "groq": "llama-3.1-8b-instant",
    "together": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "ollama": "llama3.1",
    "openai": "gpt-4o-mini",
    "openai_compatible": "llama-3.1-8b-instant"
}
LLM_MODEL = os.getenv("LLM_MODEL", default_models.get(LLM_PROVIDER, "llama-3.1-8b-instant"))

# Embedding settings
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

def get_db_path() -> str:
    """Returns absolute path to chroma db database directory."""
    return str(CHROMA_DB_DIR)

def get_log_path() -> str:
    """Returns absolute path to logging output file."""
    return str(LOGS_DIR / "app.log")

def get_data_facts_path() -> str:
    """Returns path to sports facts data file."""
    return str(DATA_DIR / "sports_facts.json")
