"""
Integration module for LlamaIndex-based agents with the main ArbitrageX application
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from .database import get_db
from .llamaindex_agents import (
    OrchestratorAgent,
    DataIngestionAgent,
    SearchAgent,
    WebCrawlerAgent,
    InformationExtractionAgent,
    AnalysisAgent,
    StorageAgent
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/llamaindex", tags=["llamaindex"])

# Initialize agent instances
def get_orchestrator_agent(db: Session = Depends(get_db)):
    """Get or create an orchestrator agent instance"""
    return OrchestratorAgent(db)

def get_data_ingestion_agent(db: Session = Depends(get_db)):
    """Get or create a data ingestion agent instance"""
    return DataIngestionAgent(db)

def get_search_agent(db: Session = Depends(get_db)):
    """Get or create a search agent instance"""
    return SearchAgent(db)

def get_web_crawler_agent(db: Session = Depends(get_db)):
    """Get or create a web crawler agent instance"""
    return WebCrawlerAgent(db)

def get_information_extraction_agent(db: Session = Depends(get_db)):
    """Get or create an information extraction agent instance"""
    return InformationExtractionAgent(db)

def get_analysis_agent(db: Session = Depends(get_db)):
    """Get or create an analysis agent instance"""
    return AnalysisAgent(db)

def get_storage_agent(db: Session = Depends(get_db)):
    """Get or create a storage agent instance"""
    return StorageAgent(db)

# API endpoints
@router.post("/orchestrate", response_model=Dict[str, Any])
async def orchestrate_task(
    agent_type: str,
    task_type: str,
    params: Dict[str, Any],
    orchestrator: OrchestratorAgent = Depends(get_orchestrator_agent)
):
    """Orchestrate a task using the LlamaIndex-based agent system"""
    try:
        task_id = await orchestrator.create_task(agent_type, task_type, params)
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Task of type {task_type} created for agent {agent_type}"
        }
    except Exception as e:
        logger.error(f"Error orchestrating task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error orchestrating task: {str(e)}")

@router.post("/search", response_model=Dict[str, Any])
async def search(
    query: str,
    search_agent: SearchAgent = Depends(get_search_agent)
):
    """Perform a web search using the LlamaIndex-based search agent"""
    try:
        result = await search_agent.web_search({"query": query})
        return result
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error performing search: {str(e)}")

@router.post("/crawl", response_model=Dict[str, Any])
async def crawl_url(
    url: str,
    crawler_agent: WebCrawlerAgent = Depends(get_web_crawler_agent)
):
    """Crawl a URL using the LlamaIndex-based web crawler agent"""
    try:
        result = await crawler_agent.crawl_url({"url": url})
        return result
    except Exception as e:
        logger.error(f"Error crawling URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error crawling URL: {str(e)}")

@router.post("/extract", response_model=Dict[str, Any])
async def extract_information(
    text: str,
    extraction_agent: InformationExtractionAgent = Depends(get_information_extraction_agent)
):
    """Extract information from text using the LlamaIndex-based information extraction agent"""
    try:
        result = await extraction_agent.extract_information({"text": text})
        return result
    except Exception as e:
        logger.error(f"Error extracting information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting information: {str(e)}")

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_companies(
    strategy_id: int,
    filters: Optional[Dict[str, Any]] = None,
    analysis_agent: AnalysisAgent = Depends(get_analysis_agent)
):
    """Analyze companies using the LlamaIndex-based analysis agent"""
    try:
        params = {
            "strategy_id": strategy_id,
            "filters": filters or {}
        }
        result = await analysis_agent.analyze_companies(params)
        return result
    except Exception as e:
        logger.error(f"Error analyzing companies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing companies: {str(e)}")

@router.post("/store", response_model=Dict[str, Any])
async def store_document_vectors(
    document_id: int,
    text_content: str,
    storage_agent: StorageAgent = Depends(get_storage_agent)
):
    """Store document vectors using the LlamaIndex-based storage agent"""
    try:
        params = {
            "document_id": document_id,
            "text_content": text_content
        }
        result = await storage_agent.store_document_vectors(params)
        return result
    except Exception as e:
        logger.error(f"Error storing document vectors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error storing document vectors: {str(e)}")

@router.post("/query", response_model=Dict[str, Any])
async def query_vectors(
    query: str,
    document_ids: Optional[List[int]] = None,
    storage_agent: StorageAgent = Depends(get_storage_agent)
):
    """Query vector store using the LlamaIndex-based storage agent"""
    try:
        params = {
            "query": query,
            "document_ids": document_ids
        }
        result = await storage_agent.query_vectors(params)
        return result
    except Exception as e:
        logger.error(f"Error querying vectors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying vectors: {str(e)}")
