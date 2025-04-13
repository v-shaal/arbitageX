from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
import logging
from typing import Dict, Any, List, Optional
import json
import requests
from bs4 import BeautifulSoup
import nltk
from datetime import datetime
import os
from tavily import TavilyClient
from dotenv import load_dotenv
import re
from .ai_components import InformationExtractor
from playwright.async_api import async_playwright
from fastapi import BackgroundTasks

# Load environment variables (ensure .env file is in project root or vars are set)
load_dotenv()

# Download necessary NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt_tab', quiet=True)
except:
    pass  # Handle silently for MVP

from .database import get_db
from . import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    Central coordinator that manages workflow between all other agents.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.agents = {
            "data_ingestion": DataIngestionAgent(db),
            "search": SearchAgent(db),
            "web_crawler": WebCrawlerAgent(db),
            "information_extraction": InformationExtractionAgent(db),
            "analysis": AnalysisAgent(db),
            "storage": StorageAgent(db)
        }
    
    async def process_task(self, task_id: int):
        logger.info(f"Orchestrator attempting to process task {task_id}...")
        task = self.db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found in DB during processing.")
            return

        logger.info(f"Task {task_id} found. Current status: {task.status}")
        if task.status in ["completed", "failed"]:
             logger.warning(f"Task {task_id} already processed with status: {task.status}. Skipping.")
             return
             
        try:
            logger.info(f"Setting task {task_id} status to 'running'.")
            task.status = "running"
            task.started_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Task {task_id} status committed as 'running'.")
        except Exception as e_stat:
             logger.error(f"ERROR setting task {task_id} status to running: {e_stat}. Rolling back.")
             self.db.rollback()
             return

        is_orchestration_task = False
        try:
            logger.info(f"Routing task {task_id} (Agent: {task.agent_type}, Type: {task.task_type})")
            if task.agent_type == "orchestration":
                is_orchestration_task = True
                if task.task_type == "generate_full_profile":
                    await self.handle_generate_full_profile(task)
                else:
                    raise ValueError(f"Unknown orchestration task type: {task.task_type}")
            elif task.agent_type == "data_ingestion":
                await self.agents["data_ingestion"].process_task(task)
            elif task.agent_type == "search":
                logger.info(f"Delegating task {task_id} to SearchAgent.")
                await self.agents["search"].process_task(task)
            elif task.agent_type == "web_crawler":
                await self.agents["web_crawler"].process_task(task)
            elif task.agent_type == "information_extraction":
                await self.agents["information_extraction"].process_task(task)
            elif task.agent_type == "analysis":
                await self.agents["analysis"].process_task(task)
            elif task.agent_type == "storage":
                await self.agents["storage"].process_task(task)
            else:
                logger.error(f"Unknown agent type encountered: {task.agent_type}")
                raise ValueError(f"Unknown agent type: {task.agent_type}")
            
            if not is_orchestration_task:
                 logger.info(f"Task {task_id} agent processing completed. Setting status to 'completed'.")
                 task.status = "completed" 
                 task.completed_at = datetime.utcnow()
                 if task.result is None:
                      task.result = {"status": "success", "message": f"Agent task {task.agent_type}/{task.task_type} completed."}
                 self.db.commit()
                 logger.info(f"Task {task_id} final status committed as 'completed'.")
            else:
                 logger.info(f"Orchestration task {task_id} handler finished. Status managed within handler.")

        except Exception as e:
            logger.error(f"Core processing error for task {task_id}: {str(e)}. Setting status to 'failed'.")
            self.db.rollback()
            task = self.db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
            if task:
                 task.status = "failed"
                 task.error = str(e)
                 task.completed_at = datetime.utcnow()
                 try:
                     self.db.commit()
                     logger.info(f"Task {task_id} final status committed as 'failed'.")
                 except Exception as e_fail:
                     logger.error(f"ERROR committing 'failed' status for task {task_id}: {e_fail}")
                     self.db.rollback()
            else:
                 logger.error(f"Task {task_id} not found when trying to set final 'failed' status.")
    
    async def create_task(self, agent_type: str, task_type: str, params: Dict[str, Any] = None) -> int:
        """Create a new task record and return its ID. Does NOT schedule processing."""
        task = models.AgentTask(
            agent_type=agent_type,
            task_type=task_type,
            status="pending",
            params=params
        )
        self.db.add(task)
        try:
            self.db.commit()
            self.db.refresh(task)
            return task.id
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create/commit task record {agent_type}/{task_type}: {e}")
            raise
    
    async def process_pending_tasks(self):
        """Process all pending tasks"""
        pending_tasks = self.db.query(models.AgentTask).filter(models.AgentTask.status == "pending").all()
        tasks = []
        for task in pending_tasks:
            tasks.append(self.process_task(task.id))
        
        if tasks:
            await asyncio.gather(*tasks)

    # --- Orchestration Handlers ---
    async def handle_generate_full_profile(self, master_task: models.AgentTask):
        """Handles the first step of generating a profile: creating the search task."""
        company_id = master_task.params.get("company_id")
        company_name = master_task.params.get("company_name")
        
        if not company_id or not company_name:
             master_task.error = "Missing company_id or company_name in master task params."
             raise ValueError("Missing company_id or company_name for profile generation.")
             
        logger.info(f"Initiating profile generation for {company_name} (ID: {company_id}) from master task {master_task.id}")
        
        # Step 1: Create Search Query & Search Task Record
        # Check if a search query already exists for this company name to avoid duplicates
        search_query = self.db.query(models.SearchQuery).filter(models.SearchQuery.query_text == company_name).first()
        if not search_query:
            search_query = models.SearchQuery(query_text=company_name, target_entity=company_name)
            self.db.add(search_query)
            
        search_task_params = {"query": company_name, "target_entity": company_name, "max_results": 5}
        # Call create_task WITHOUT background_tasks_obj to ONLY create the record
        search_task_id = await self.create_task(
            agent_type="search",
            task_type="web_search",
            params=search_task_params
        )
        
        logger.info(f"Created search task record {search_task_id} for company {company_name}. It needs to be scheduled/processed separately.")
        
        # Set the master task's result and status appropriately
        master_task.result = {
            "status": "sub_task_created",
            "message": f"Created search task {search_task_id}. Trigger sub-task processing to continue.",
            "search_task_id": search_task_id
        }
        # Keep master task as 'running' because the overall profile generation is not complete
        master_task.status = "running" 
        self.db.commit()
        
        # --- Chaining Logic is NOT implemented here --- 


class DataIngestionAgent:
    """
    Handles all data input operations and initial preprocessing.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_task(self, task: models.AgentTask):
        """Process a data ingestion task"""
        if task.task_type == "process_csv":
            await self.process_csv(task.params)
        elif task.task_type == "process_strategy":
            await self.process_strategy(task.params)
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")
    
    async def process_csv(self, params: Dict[str, Any]):
        """Process CSV data"""
        # In a full implementation, this would handle more complex CSV processing
        # For MVP, basic processing is done in the API endpoint
        logger.info(f"Processing CSV with params: {params}")
        
        # Update task result
        return {"status": "success", "message": "CSV processed successfully"}
    
    async def process_strategy(self, params: Dict[str, Any]):
        """Process strategy document"""
        # In a full implementation, this would extract criteria from documents
        # For MVP, we'll use a simplified approach
        logger.info(f"Processing strategy document with params: {params}")
        
        # Update task result
        return {"status": "success", "message": "Strategy processed successfully"}


class SearchAgent:
    """
    Performs targeted web searches using Tavily API.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # Initialize Tavily Client with API key from environment
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    async def process_task(self, task: models.AgentTask):
        logger.info(f"SearchAgent starting process_task for task {task.id}")
        if task.task_type == "web_search":
            try:
                # Perform the search and store results
                result_summary = await self.web_search(task.params, task.id)
                task.result = result_summary
                # Note: Status is set to completed by the OrchestratorAgent
                return result_summary
            except Exception as e:
                # Log the error and let the orchestrator handle setting task status to failed
                logger.error(f"Search task {task.id} failed: {str(e)}")
                task.error = f"Search failed: {str(e)}"
                # Re-raise the exception so the orchestrator knows it failed
                raise e 
        else:
            logger.warning(f"SearchAgent received unknown task type: {task.task_type} for task {task.id}")
            raise ValueError(f"Unknown task type: {task.task_type}")
    
    async def web_search(self, params: Dict[str, Any], task_id: int):
        logger.info(f"SearchAgent starting web_search for task {task_id}")
        query = params.get("query")
        # target_entity = params.get("target_entity") # Can be used for Tavily context if needed
        max_results = params.get("max_results", 5) # Default to 5 results

        if not query:
            raise ValueError("Search query is required")
        
        if not self.tavily_client.api_key:
            raise ValueError("Tavily API key not configured. Set TAVILY_API_KEY environment variable.")

        # Find the associated SearchQuery record using the task parameters
        # Note: This assumes the SearchQuery was created before the task
        # A more robust approach might pass search_query_id in task params
        search_query_record = self.db.query(models.SearchQuery).filter(
            models.SearchQuery.query_text == query
        ).order_by(models.SearchQuery.search_date.desc()).first()
        
        if not search_query_record:
             # Optionally create one if it doesn't exist, or raise error
             # For now, we raise an error, assuming SearchQuery is created via /api/search endpoint first
             raise ValueError(f"SearchQuery record not found for query: '{query}'")
        
        logger.info(f"Performing Tavily search for task {task_id}, query: '{query}'")

        # Perform search using Tavily client
        # Use search_depth='advanced' for potentially better context, but costs more credits
        tavily_response = self.tavily_client.search(query=query, search_depth="basic", max_results=max_results)
        
        search_results_stored = 0
        if tavily_response and 'results' in tavily_response:
            for rank_index, result in enumerate(tavily_response['results']):
                # Create and store SearchResult record
                db_search_result = models.SearchResult(
                    query_id=search_query_record.id,
                    title=result.get('title', 'No Title')[:511], # Truncate if needed
                    url=result.get('url', '')[:511],
                    snippet=result.get('content', '')[:1023], # Use 'content' as snippet
                    rank=rank_index + 1, # Use index as rank
                    is_processed=False # Mark as unprocessed initially
                )
                self.db.add(db_search_result)
                search_results_stored += 1
                
            # Update the result count on the SearchQuery record
            search_query_record.result_count = search_results_stored
            self.db.commit()
            logger.info(f"Stored {search_results_stored} results for search query ID {search_query_record.id}")
        else:
             logger.warning(f"Tavily search returned no results for query: '{query}'")

        # Return a summary for the task result field
        return {
            "status": "success",
            "message": f"Search completed. Found {search_results_stored} results for query: '{query}'.",
            "results_stored_count": search_results_stored,
            "search_query_id": search_query_record.id
            # Avoid returning full results here to keep task result small
        }


class WebCrawlerAgent:
    """
    Fetches and extracts content from web URLs using Playwright.
    """

    def __init__(self, db: Session):
        self.db = db
        # No specific init needed for playwright here, 
        # but could add shared browser context later if optimizing

    async def process_task(self, task: models.AgentTask):
        """Process a web crawl task"""
        if task.task_type == "crawl_url":
            try:
                # Using Playwright now
                result = await self.crawl_url_playwright(task.params)
                task.result = result
                if result.get('status') == 'success' and task.params.get('search_result_id'):
                    self.update_search_result_processed(task.params['search_result_id'], True)
                return result
            except Exception as e:
                logger.error(f"Crawl task {task.id} failed for URL {task.params.get('url')}: {str(e)}")
                task.error = f"Crawl failed: {str(e)}"
                if task.params.get('search_result_id'):
                     self.update_search_result_processed(task.params['search_result_id'], True, success=False)
                raise e # Re-raise to mark task as failed in orchestrator
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")

    async def crawl_url_playwright(self, params: Dict[str, Any]):
        """Crawl a single URL using Playwright."""
        url = params.get("url")
        search_result_id = params.get("search_result_id")
        timeout_ms = 30000 # 30 seconds timeout for navigation

        if not url:
            raise ValueError("URL is required for crawling")

        logger.info(f"Crawling URL with Playwright: {url} (linked to SearchResult: {search_result_id}) ")

        extracted_content = ""
        page_title = "No Title Found"
        final_status = "failed"

        try:
            async with async_playwright() as p:
                # Launch browser (chromium is often good, but could use firefox or webkit)
                # Headless=True runs without a visible browser window
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to the URL with a timeout
                try:
                    await page.goto(url, timeout=timeout_ms, wait_until='domcontentloaded') 
                    # wait_until options: 'load', 'domcontentloaded', 'networkidle', 'commit'
                    # 'domcontentloaded' is usually a good balance
                except Exception as nav_error:
                    # Handle navigation errors (timeouts, invalid URL, etc.)
                    logger.error(f"Playwright navigation error for {url}: {nav_error}")
                    await browser.close()
                    raise ValueError(f"Failed to navigate to URL {url}: {nav_error}") from nav_error

                # Wait for potential dynamic content (example: wait 2 seconds)
                # More specific waits are better: page.wait_for_selector(...) etc.
                await page.wait_for_timeout(2000) 

                # Extract basic information
                page_title = await page.title()
                
                # Extract text content from the body
                # This gets all visible text; might need refinement for specific sites
                body_content = await page.locator('body').inner_text()
                extracted_content = re.sub(r'\s+', ' ', body_content).strip()

                # Close the browser
                await browser.close()
                final_status = "success"
                logger.info(f"Successfully crawled URL with Playwright: {url}")

        except Exception as e:
            # Catch any other Playwright or processing errors
            logger.error(f"Playwright execution error for {url}: {e}")
            # Ensure browser is closed if error occurred mid-process
            # This might require more complex context management in real-world scenarios
            raise ValueError(f"Playwright execution failed for {url}: {e}") from e

        # Limit content size
        max_length = 5000
        content_snippet = extracted_content[:200] + "..." if len(extracted_content) > 200 else extracted_content
        if len(extracted_content) > max_length:
            extracted_content_limited = extracted_content[:max_length] + "... (truncated)"
        else:
            extracted_content_limited = extracted_content
            
        # Return structured result
        crawl_result = {
            "status": final_status,
            "url": url,
            "title": page_title,
            "extracted_content_snippet": content_snippet,
            "content_length": len(extracted_content),
            # Store the limited content, or handle full content storage separately
            "full_content_limited": extracted_content_limited 
        }

        # Note: Triggering next agent (e.g., extraction) would happen after this return, 
        # potentially based on crawl_result["status"]

        return crawl_result
            
    def update_search_result_processed(self, search_result_id: int, status: bool, success: bool = True):
        """Updates the is_processed flag of a SearchResult record."""
        try:
            search_result = self.db.query(models.SearchResult).filter(models.SearchResult.id == search_result_id).first()
            if search_result:
                search_result.is_processed = status
                # Optionally add more details, like crawl status
                # search_result.crawl_status = "success" if success else "failed"
                self.db.commit()
                logger.info(f"Updated is_processed={status} for SearchResult ID {search_result_id}")
            else:
                logger.warning(f"Could not find SearchResult ID {search_result_id} to update status.")
        except Exception as e:
            logger.error(f"Failed to update is_processed status for SearchResult ID {search_result_id}: {e}")
            self.db.rollback() # Rollback if update fails
            
    # Optional: Method to create extraction task
    # async def create_extraction_task(self, url: str, content: str, search_result_id: int):
    #     db_task = models.AgentTask(
    #         agent_type="information_extraction",
    #         task_type="extract_from_content",
    #         status="pending",
    #         params={"source_url": url, "content": content, "search_result_id": search_result_id} 
    #     )
    #     self.db.add(db_task)
    #     self.db.commit()
    #     self.db.refresh(db_task)
    #     # Can't use background_tasks here, need Orchestrator 
    #     # orchestrator = OrchestratorAgent(self.db) # Avoid circular dependency if possible
    #     # await orchestrator.process_task(db_task.id) # This needs careful handling
    #     logger.info(f"Created extraction task {db_task.id} for URL {url}")


class InformationExtractionAgent:
    """
    Extracts structured information from text content.
    """

    def __init__(self, db: Session):
        self.db = db
        # Initialize the actual InformationExtractor component
        self.extractor = InformationExtractor()

    async def process_task(self, task: models.AgentTask):
        """Process an information extraction task using the LLM extractor."""
        if task.task_type == "extract_from_content": 
            try:
                # Call the new LLM-based extraction method
                result = await self.extract_information_llm(task.params)
                task.result = result # Store the ExtractedData Pydantic object (or its dict representation)
                return result
            except Exception as e:
                logger.error(f"LLM Extraction task {task.id} failed: {str(e)}")
                task.error = f"LLM Extraction failed: {str(e)}"
                raise e
        else:
            raise ValueError(f"Unknown task type for InformationExtractionAgent: {task.task_type}")

    async def extract_information_llm(self, params: Dict[str, Any]):
        """Extract information from the provided content using LLM."""
        # Get content - use the limited content from Playwright for now
        # In production, might store full content elsewhere and fetch here
        content = params.get("content") # Assuming 'content' key holds the text
        if not content:
            # Fallback check if playwright stored under different key
            content = params.get("full_content_limited")
            
        source_url = params.get("source_url", "Unknown")
        # You might want to pass the original query target as company context
        # company_context = params.get("original_target_entity") 
        
        if not content:
            logger.warning(f"No content found in params for extraction (source: {source_url}). Skipping.")
            return {"status": "skipped", "message": "No content provided for extraction."} # Return dict

        logger.info(f"Extracting information (LLM) from content sourced from: {source_url}")

        # Use the InformationExtractor component's new method
        extracted_data: ExtractedData = self.extractor.extract_structured_data_with_llm(
            text=content, 
            # company_context=company_context # Optional context
        )
        
        logger.info(f"Successfully processed LLM extraction for: {source_url}")

        # Return the results as a dictionary for JSON serialization in the task result
        return {
            "status": "success",
            "source_url": source_url,
            "extracted_data": extracted_data.dict() # Convert Pydantic model to dict
        }
        
    # Optional: Method to store extracted data
    # def store_extracted_data(self, extracted_data: Dict, search_result_id: Optional[int]): ...


class AnalysisAgent:
    """
    Evaluates companies against investment criteria and generates insights.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_task(self, task: models.AgentTask):
        """Process an analysis task"""
        if task.task_type == "company_analysis":
            result = await self.analyze_companies(task.params)
            task.result = result
            return result
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")
    
    async def analyze_companies(self, params: Dict[str, Any]):
        """Analyze companies against investment strategy"""
        strategy_id = params.get("strategy_id")
        filters = params.get("filters", {})
        
        if not strategy_id:
            raise ValueError("Strategy ID is required")
        
        # Get strategy from database
        strategy = self.db.query(models.InvestmentStrategy).filter(
            models.InvestmentStrategy.id == strategy_id
        ).first()
        
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")
        
        # Get companies from database
        query = self.db.query(models.Company)
        
        # Apply filters
        if filters.get("industry"):
            query = query.filter(models.Company.industry == filters["industry"])
        
        if filters.get("location"):
            query = query.filter(models.Company.location.like(f"%{filters['location']}%"))
        
        companies = query.all()
        
        # For MVP, we'll use a simple scoring approach
        results = []
        for company in companies:
            # Get financial metrics
            metrics = self.db.query(models.FinancialMetric).filter(
                models.FinancialMetric.company_id == company.id
            ).all()
            
            # Calculate score (simplified for MVP)
            score = 0.0
            score_breakdown = {}
            
            # Industry match
            if company.industry and strategy.name and company.industry.lower() in strategy.name.lower():
                score += 0.3
                score_breakdown["industry_match"] = 0.3
            else:
                score_breakdown["industry_match"] = 0.0
            
            # Revenue score
            revenue_metric = next((m for m in metrics if m.metric_type == "revenue"), None)
            if revenue_metric:
                # Simple scoring based on revenue
                if revenue_metric.value > 50000000:  # $50M+
                    score += 0.3
                    score_breakdown["revenue"] = 0.3
                elif revenue_metric.value > 10000000:  # $10M+
                    score += 0.2
                    score_breakdown["revenue"] = 0.2
                else:
                    score += 0.1
                    score_breakdown["revenue"] = 0.1
            else:
                score_breakdown["revenue"] = 0.0
            
            # Growth score
            growth_metric = next((m for m in metrics if m.metric_type == "growth_rate"), None)
            if growth_metric:
                # Simple scoring based on growth rate
                if growth_metric.value > 30:  # 30%+
                    score += 0.4
                    score_breakdown["growth"] = 0.4
                elif growth_metric.value > 15:  # 15%+
                    score += 0.3
                    score_breakdown["growth"] = 0.3
                else:
                    score += 0.1
                    score_breakdown["growth"] = 0.1
            else:
                score_breakdown["growth"] = 0.0
            
            # Create analysis result
            explanation = f"Company scored {score:.2f} based on industry match, revenue, and growth metrics."
            if score > 0.6:
                explanation += " This company is a strong match for the investment strategy."
            elif score > 0.3:
                explanation += " This company is a moderate match for the investment strategy."
            else:
                explanation += " This company is a weak match for the investment strategy."
            
            analysis_result = models.AnalysisResult(
                company_id=company.id,
                strategy_id=strategy_id,
                overall_score=score,
                explanation=explanation,
                score_breakdown=score_breakdown
            )
            self.db.add(analysis_result)
            
            results.append({
                "company_id": company.id,
                "company_name": company.name,
                "score": score,
                "explanation": explanation
            })
        
        # Commit changes
        self.db.commit()
        
        return {
            "status": "success",
            "message": f"Analyzed {len(companies)} companies against strategy {strategy_id}",
            "results": results
        }


class StorageAgent:
    """
    Manages data persistence and retrieval operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_task(self, task: models.AgentTask):
        """Process a storage task"""
        # Ensure db session is active (relevant if not using run_task_processor wrapper)
        if not self.db.is_active:
            logger.warning(f"StorageAgent DB session inactive for task {task.id}. Attempting reconnect/refresh (not implemented).")
            # In a real scenario, might need session refresh logic here
            # For now, we assume the session provided by run_task_processor is valid.

        if task.task_type == "store_extracted_data":
            result = await self.store_extracted_data(task.params)
        elif task.task_type == "store_company_overview":
            result = await self.store_company_overview(task.params)
        elif task.task_type == "store_company_links":
            result = await self.store_company_links(task.params)
        # Keep existing vector storage tasks if needed
        elif task.task_type == "store_document_vectors":
            result = await self.store_document_vectors(task.params)
        elif task.task_type == "store_company_vectors":
            result = await self.store_company_vectors(task.params)
        else:
            raise ValueError(f"Unknown task type for StorageAgent: {task.task_type}")
        
        task.result = result
        return result # Return result summary

    async def store_extracted_data(self, params: Dict[str, Any]):
        """Store extracted metrics and events linked to a company."""
        company_id = params.get("company_id")
        extracted_data = params.get("extracted_data") # This is the dict from ExtractedData model
        source_url = params.get("source_url", "Unknown Source")

        if not company_id or not extracted_data:
            raise ValueError("company_id and extracted_data are required for storage.")

        company = self.db.query(models.Company).filter(models.Company.id == company_id).first()
        if not company:
            logger.warning(f"Company ID {company_id} not found. Cannot store extracted data.")
            return {"status": "failed", "message": f"Company ID {company_id} not found."}

        metrics_stored = 0
        events_stored = 0

        # Store Metrics
        if extracted_data.get("metrics"):
            for metric_data in extracted_data["metrics"]:
                if metric_data.get("metric_type") and metric_data.get("value") is not None:
                    # Basic type mapping (can be more sophisticated)
                    db_metric = models.FinancialMetric(
                        company_id=company_id,
                        metric_type=metric_data.get("metric_type", "unknown")[:50], # Ensure length
                        value=float(metric_data["value"]),
                        unit=metric_data.get("unit", "unknown")[:20],
                        time_period=metric_data.get("period", "unknown")[:50],
                        source=f"LLM Extraction from {source_url}"
                        # Add confidence score if available
                    )
                    self.db.add(db_metric)
                    metrics_stored += 1

        # Store Events
        if extracted_data.get("events"):
            for event_data in extracted_data["events"]:
                if event_data.get("event_type") and event_data.get("details"):
                    db_event = models.CompanyEvent(
                        company_id=company_id,
                        event_type=event_data.get("event_type", "unknown")[:50],
                        description=event_data.get("details", "")[:1023], # Ensure length
                        event_date=self._parse_event_date(event_data.get("date")),
                        source=f"LLM Extraction from {source_url}"
                        # Add amount if extracted
                    )
                    self.db.add(db_event)
                    events_stored += 1

        try:
            self.db.commit()
            logger.info(f"Stored {metrics_stored} metrics and {events_stored} events for Company ID {company_id}.")
            return {
                "status": "success",
                "message": f"Stored {metrics_stored} metrics and {events_stored} events.",
                "metrics_stored": metrics_stored,
                "events_stored": events_stored
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database error storing extracted data for Company ID {company_id}: {e}")
            raise ValueError(f"DB error storing data: {e}") from e
            
    def _parse_event_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Attempt to parse various date formats."""
        if not date_str:
            return None
        # Add more formats as needed
        formats = ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        logger.warning(f"Could not parse date string: {date_str}")
        return None # Or default to now: datetime.utcnow()
        
    async def store_company_overview(self, params: Dict[str, Any]):
        """Store or update the company overview/description."""
        company_id = params.get("company_id")
        overview = params.get("overview")

        if not company_id or overview is None: # Allow empty string
            raise ValueError("company_id and overview are required.")

        company = self.db.query(models.Company).filter(models.Company.id == company_id).first()
        if not company:
            logger.warning(f"Company ID {company_id} not found. Cannot store overview.")
            return {"status": "failed", "message": f"Company ID {company_id} not found."}
            
        try:
            company.description = overview # Update the description field
            self.db.commit()
            logger.info(f"Updated overview for Company ID {company_id}.")
            return {"status": "success", "message": "Company overview updated."}
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database error storing overview for Company ID {company_id}: {e}")
            raise ValueError(f"DB error storing overview: {e}") from e
            
    async def store_company_links(self, params: Dict[str, Any]):
        """Store source links for a company."""
        company_id = params.get("company_id")
        links = params.get("links") # Expecting list of dicts: {"url": ..., "description": ..., "link_type": ...}
        overwrite = params.get("overwrite", False) # Option to replace existing links

        if not company_id or not isinstance(links, list):
            raise ValueError("company_id and a list of links are required.")

        company = self.db.query(models.Company).filter(models.Company.id == company_id).first()
        if not company:
            logger.warning(f"Company ID {company_id} not found. Cannot store links.")
            return {"status": "failed", "message": f"Company ID {company_id} not found."}

        if overwrite:
            # Delete existing links for this company if overwriting
            self.db.query(models.CompanySourceLink).filter(models.CompanySourceLink.company_id == company_id).delete()
            logger.info(f"Deleted existing links for Company ID {company_id} due to overwrite flag.")
            
        links_stored = 0
        for link_data in links:
            if link_data.get("url"):
                # Basic type mapping
                db_link = models.CompanySourceLink(
                    company_id=company_id,
                    url=link_data["url"][:1023], # Ensure length
                    description=link_data.get("description", None),
                    link_type=link_data.get("link_type", "other")[:50]
                )
                self.db.add(db_link)
                links_stored += 1
        
        try:
            self.db.commit()
            logger.info(f"Stored {links_stored} links for Company ID {company_id}.")
            return {
                "status": "success",
                "message": f"Stored {links_stored} links.",
                "links_stored": links_stored
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database error storing links for Company ID {company_id}: {e}")
            raise ValueError(f"DB error storing links: {e}") from e

    # Keep existing vector storage methods
    async def store_document_vectors(self, params: Dict[str, Any]):
        logger.info(f"Processing document vectors with params: {params}")
        # Placeholder - implement actual vector storing logic if needed
        return {"status": "success", "message": "Document vectors processed (placeholder)."}

    async def store_company_vectors(self, params: Dict[str, Any]):
        logger.info(f"Processing company vectors with params: {params}")
        # Placeholder - implement actual vector storing logic if needed
        return {"status": "success", "message": "Company vectors processed (placeholder)."}


# Dependency to get orchestrator
def get_orchestrator(db: Session = Depends(get_db)):
    return OrchestratorAgent(db)
