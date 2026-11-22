"""SentinelOps package setup."""
import os

from dotenv import load_dotenv

load_dotenv()

# The GenAI SDK and ADK use different documented names across versions.
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
