#!/usr/bin/env python3
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Import backend routers
from arbitagex.backend.main import router as main_router
from arbitagex.backend.agent_api import router as agent_router
from arbitagex.backend.llamaindex_integration import router as llamaindex_router
from arbitagex.backend.database import engine, Base # For table creation

# --- LlamaIndex Global Settings --- 
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding # Or your chosen embedding

# Create main FastAPI app
app = FastAPI(title="ArbitrageX - Combined API")

# Create database tables on startup (optional)
load_dotenv()

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# Configure CORS (Apply to main app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure LlamaIndex settings globally BEFORE importing other modules
print("Configuring global LlamaIndex settings...")
# UPDATE: Use the specific Gemini 1.5 Pro model identifier requested
Settings.llm = Gemini(model_name="models/gemini-2.5-pro-preview-03-25") 
# Optionally configure embeddings globally too
# Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001") 
# Access model name via .model attribute
print(f"LLM set to: {type(Settings.llm)} with model name: {Settings.llm.model}") 
# print(f"Embedding model set to: {type(Settings.embed_model)}")
# --- End LlamaIndex Global Settings ---

# Include backend routers with prefix
app.include_router(main_router, prefix="/api")
app.include_router(agent_router, prefix="/api") # agent_router already has /agents prefix internally
app.include_router(llamaindex_router, prefix="/api") # llamaindex_router already has /llamaindex prefix internally

# Mount static files for frontend at the root path
# Ensure this path is correct relative to where run.py is executed
static_files_path = os.path.join(os.path.dirname(__file__), "arbitagex/frontend")
app.mount("/", StaticFiles(directory=static_files_path, html=True), name="frontend")

# Removed direct mounting of backend_app
# app.mount("/api", backend_app)

if __name__ == "__main__":
    # Run the application
    uvicorn.run("run:app", host="0.0.0.0", port=8080, reload=True) # Use reload for development
