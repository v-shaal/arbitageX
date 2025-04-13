import asyncio
import logging
import os
import sys # Import sys
from dotenv import load_dotenv

# --- Add Project Root to sys.path --- 
# Calculate the project root directory (two levels up from tests/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added project root to sys.path: {project_root}")
# --- End Path Addition ---

# --- LlamaIndex Global Settings (Copied from run.py for standalone testing) ---
# TODO: Move this config to a shared module (e.g., config.py)
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
# from llama_index.embeddings.gemini import GeminiEmbedding # Optional

# Load environment variables (like GOOGLE_API_KEY)
load_dotenv()

# Configure LlamaIndex settings globally
print("Configuring global LlamaIndex settings for test...")
try:
    # Use the same model configured in run.py
    Settings.llm = Gemini(model_name="models/gemini-1.5-pro-002")
    # Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001") # Optional
    print(f"LLM set to: {type(Settings.llm)} with model name: {Settings.llm.model}")
    # print(f"Embedding model set to: {type(Settings.embed_model)}")
except Exception as e:
    print(f"Error configuring LlamaIndex settings: {e}")
    print("Ensure GOOGLE_API_KEY is set and necessary packages are installed.")
    exit(1) # Stop if LLM cannot be configured
# --- End LlamaIndex Global Settings ---

# Import the function to test
from arbitagex.backend.orchestration import run_profile_generation

# --- Configuration for the Test ---
TARGET_COMPANY_ID = 66 # Example: Embark IT, Inc. (Use a valid ID from your DB)
TARGET_COMPANY_NAME = "Prime Communications, Inc."
# --- End Test Configuration ---

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# --- End Logging Setup ---


async def main():
    """Runs the orchestration test."""
    if not TARGET_COMPANY_ID or not TARGET_COMPANY_NAME:
        logging.error("TARGET_COMPANY_ID and TARGET_COMPANY_NAME must be set.")
        return

    logging.info(f"--- Starting Test for Company ID: {TARGET_COMPANY_ID}, Name: {TARGET_COMPANY_NAME} ---")
    try:
        await run_profile_generation(
            company_id=TARGET_COMPANY_ID,
            company_name=TARGET_COMPANY_NAME
        )
    except Exception as e:
        logging.error(f"Test execution failed: {e}", exc_info=True)
    logging.info("--- Test Finished ---")

if __name__ == "__main__":
    # Check if necessary environment variables are set (basic check)
    if not os.getenv("GOOGLE_API_KEY"):
         print("Error: GOOGLE_API_KEY environment variable not set.")
    else:
        asyncio.run(main())
