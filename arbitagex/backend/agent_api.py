import asyncio
import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from llama_index.core import Settings

from .database import get_db
from .agents import OrchestratorAgent
from .ai_components import (
    TextProcessor, 
    InformationExtractor,
    CompanyProfileGenerator,
    SimilarityCalculator,
    CompanyScorer
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI components
text_processor = TextProcessor()
information_extractor = InformationExtractor()
profile_generator = CompanyProfileGenerator()
similarity_calculator = SimilarityCalculator()
company_scorer = CompanyScorer()

# Initialize APIRouter
router = APIRouter(prefix="/agents", tags=["agents"])

# Define request body model
class TextPayload(BaseModel):
    text: str

class GenerateProfilePayload(BaseModel):
    company_name: str
    texts: list[str]

# Background task to process pending agent tasks
async def process_pending_tasks(db: Session):
    """Process all pending agent tasks in the background"""
    orchestrator = OrchestratorAgent(db)
    await orchestrator.process_pending_tasks()

# Endpoints attached to the router
@router.post("/process-tasks")
async def trigger_process_tasks(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger processing of pending agent tasks"""
    background_tasks.add_task(process_pending_tasks, db)
    return {"status": "processing", "message": "Processing pending tasks in background"}

@router.post("/extract-information")
async def extract_information(payload: TextPayload, db: Session = Depends(get_db)):
    """Extract information from text using AI components"""
    cleaned_text = text_processor.clean_text(payload.text)
    financial_metrics = information_extractor.extract_financial_metrics(cleaned_text)
    events = information_extractor.extract_company_events(cleaned_text)
    try:
        embedding = Settings.embed_model.get_text_embedding(cleaned_text)
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        embedding = []
    return {
        "financial_metrics": financial_metrics,
        "events": events,
        "embedding_sample": embedding[:5]
    }

@router.post("/generate-profile")
async def generate_company_profile(payload: GenerateProfilePayload, db: Session = Depends(get_db)):
    """Generate a company profile from multiple text sources"""
    profile = profile_generator.generate_profile(payload.company_name, payload.texts)
    return profile

@router.post("/score-company")
async def score_company(company_profile: dict, strategy_criteria: dict, db: Session = Depends(get_db)):
    """Score a company based on investment criteria"""
    score_result = company_scorer.score_company(company_profile, strategy_criteria)
    return score_result

@router.post("/calculate-similarity")
async def calculate_similarity(vector1: list[float], vector2: list[float], db: Session = Depends(get_db)):
    """Calculate similarity between two vectors"""
    similarity = similarity_calculator.cosine_similarity(vector1, vector2)
    return {"similarity": similarity}
