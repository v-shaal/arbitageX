from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd
import json
import os
from typing import List, Optional
from datetime import datetime

from . import models, schemas
from .database import engine, get_db, SessionLocal
from .agents import OrchestratorAgent

# Create database tables
# models.Base.metadata.create_all(bind=engine) # Move table creation to main app startup if needed

# Initialize APIRouter instead of FastAPI app
router = APIRouter()

# --- Background Task Wrapper --- 
# This function creates an independent DB session for the background task
async def run_task_processor(task_id: int):
    db: Session | None = None # Initialize db to None
    try:
        db = SessionLocal() # Create a new session
        orchestrator = OrchestratorAgent(db=db)
        await orchestrator.process_task(task_id)
    except Exception as e:
        # Log any exceptions during background task execution
        # Consider more robust logging or error handling here
        print(f"ERROR during background task processing for task {task_id}: {e}")
        # Optionally update task status to failed directly here if needed
        if db: # Check if db session was created before trying to use it
            task = db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
            if task and task.status != "completed":
                task.status = "failed"
                task.error = f"Background execution error: {str(e)}"
                task.completed_at = datetime.utcnow()
                db.commit()
    finally:
        if db: # Ensure session is closed if it was opened
            db.close()
# --- End Background Task Wrapper ---

# Root endpoint (now relative to router prefix)
@router.get("/")
def read_root():
    return {"message": "Welcome to ArbitrageX Backend Routes", "version": "0.1.0"}

# Health check endpoint (now relative to router prefix)
@router.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Company endpoints
@router.post("/companies/", response_model=schemas.Company)
def create_company(company: schemas.CompanyCreate, db: Session = Depends(get_db)):
    db_company = models.Company(**company.dict())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

@router.get("/companies/", response_model=List[schemas.Company])
def read_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Add a filter to exclude companies where the name starts with "Test Company"
    companies = db.query(models.Company).filter(
        ~models.Company.name.startswith("Test Company")
    ).offset(skip).limit(limit).all()
    return companies

@router.get("/companies/{company_id}", response_model=schemas.Company)
def read_company(company_id: int, db: Session = Depends(get_db)):
    db_company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if db_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

# New endpoint to delete all companies named "Test Company"
@router.delete("/companies/delete-test-companies", status_code=200)
def delete_test_companies(db: Session = Depends(get_db)):
    """Deletes all company records where the name is exactly 'Test Company'."""
    # Query for the companies to be deleted
    companies_to_delete = db.query(models.Company).filter(
        models.Company.name == "Test Company"
    ).all()
    
    count = len(companies_to_delete)
    
    if count == 0:
        return {"message": "No companies named 'Test Company' found to delete."}
    
    deleted_names = []
    for company in companies_to_delete:
        deleted_names.append(company.name) # Should all be "Test Company"
        # Important: Handle related records (FinancialMetric, Person, CompanyEvent, etc.)
        # if cascade delete is not configured in the database/models.
        # Simple deletion assuming cascade or no strict foreign keys for now:
        db.delete(company)
    
    # Commit the transaction
    db.commit()
    
    return {
        "message": f"Successfully deleted {count} companies named 'Test Company'."
    }

# Investment Strategy endpoints
@router.post("/strategies/", response_model=schemas.InvestmentStrategy)
def create_strategy(strategy: schemas.InvestmentStrategyCreate, db: Session = Depends(get_db)):
    db_strategy = models.InvestmentStrategy(**strategy.dict(exclude={"criteria"}))
    db.add(db_strategy)
    db.commit()
    db.refresh(db_strategy)
    
    # Add criteria if provided
    if strategy.criteria:
        for criterion in strategy.criteria:
            db_criterion = models.StrategyCriteria(
                strategy_id=db_strategy.id,
                **criterion.dict()
            )
            db.add(db_criterion)
        db.commit()
        db.refresh(db_strategy)
    
    return db_strategy

@router.get("/strategies/", response_model=List[schemas.InvestmentStrategy])
def read_strategies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    strategies = db.query(models.InvestmentStrategy).offset(skip).limit(limit).all()
    return strategies

@router.get("/strategies/{strategy_id}", response_model=schemas.InvestmentStrategy)
def read_strategy(strategy_id: int, db: Session = Depends(get_db)):
    db_strategy = db.query(models.InvestmentStrategy).filter(models.InvestmentStrategy.id == strategy_id).first()
    if db_strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return db_strategy

# Modified endpoint to delete strategies starting with a specified prefix
@router.delete("/strategies/delete-by-prefix", status_code=200)
def delete_strategies_by_prefix(prefix: str, db: Session = Depends(get_db)):
    """Deletes all investment strategies where the name starts with the specified prefix."""
    if not prefix:
        raise HTTPException(status_code=400, detail="Prefix query parameter is required.")
        
    # Query for the strategies to be deleted based on the prefix
    strategies_to_delete = db.query(models.InvestmentStrategy).filter(
        models.InvestmentStrategy.name.startswith(prefix)
    ).all()
    
    count = len(strategies_to_delete)
    
    if count == 0:
        return {"message": f"No strategies starting with '{prefix}' found to delete."}
    
    deleted_names = []
    for strategy in strategies_to_delete:
        deleted_names.append(strategy.name)
        # db.query(models.StrategyCriteria).filter(models.StrategyCriteria.strategy_id == strategy.id).delete()
        db.delete(strategy)
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {count} strategies starting with '{prefix}'.",
        "deleted_strategy_names": deleted_names
    }

# CSV Upload endpoint
@router.post("/upload/csv/", response_model=schemas.CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    mapping_template: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Save the uploaded file temporarily
    file_location = f"/tmp/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    # Parse the CSV file
    try:
        df = pd.read_csv(file_location)
        
        # Apply mapping template if provided
        if mapping_template:
            mapping = json.loads(mapping_template)
            df = df.rename(columns=mapping)
        
        # Process the first 5 rows for preview
        preview_data = df.head(5).to_dict(orient="records")
        
        # Get column names
        columns = df.columns.tolist()
        
        # Process companies from CSV
        companies_created = 0
        for _, row in df.iterrows():
            # Basic validation
            if 'name' not in row or pd.isna(row['name']):
                continue
                
            # Create company object
            company_data = {
                'name': row.get('name', ''),
                'industry': row.get('industry', ''),
                'sub_industry': row.get('sub_industry', None),
                'location': row.get('location', None),
                'employee_count': int(row.get('employee_count', 0)) if not pd.isna(row.get('employee_count', 0)) else None,
                'website': row.get('website', None)
            }
            
            # Add to database
            db_company = models.Company(**company_data)
            db.add(db_company)
            companies_created += 1
            
            # Add financial metrics if available
            if 'revenue' in row and not pd.isna(row['revenue']):
                revenue_data = {
                    'metric_type': 'revenue',
                    'value': float(row['revenue'].replace('$', '').replace('M', '000000').replace('K', '000')) 
                            if isinstance(row['revenue'], str) else float(row['revenue']),
                    'unit': 'USD',
                    'time_period': 'Latest',
                    'source': f"CSV Import: {file.filename}"
                }
                db_metric = models.FinancialMetric(company_id=db_company.id, **revenue_data)
                db.add(db_metric)
                
            # Add growth rate if available
            if 'growth_rate' in row and not pd.isna(row['growth_rate']):
                growth_data = {
                    'metric_type': 'growth_rate',
                    'value': float(row['growth_rate'].replace('%', '')) 
                            if isinstance(row['growth_rate'], str) else float(row['growth_rate']),
                    'unit': '%',
                    'time_period': 'Annual',
                    'source': f"CSV Import: {file.filename}"
                }
                db_metric = models.FinancialMetric(company_id=db_company.id, **growth_data)
                db.add(db_metric)
        
        # Commit all changes
        db.commit()
        
        # Clean up the temporary file
        os.remove(file_location)
        
        return {
            "upload_id": file.filename,
            "status": "success",
            "row_count": len(df),
            "columns": columns,
            "preview_data": preview_data,
            "companies_created": companies_created
        }
        
    except Exception as e:
        # Clean up the temporary file
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {str(e)}")

# Strategy Document Upload endpoint
@router.post("/upload/strategy/", response_model=schemas.StrategyUploadResponse)
async def upload_strategy_document(
    file: UploadFile = File(...),
    strategy_name: str = Form(...),
    db: Session = Depends(get_db)
):
    # Save the uploaded file temporarily
    file_location = f"/tmp/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    # Create a new strategy
    db_strategy = models.InvestmentStrategy(
        name=strategy_name,
        description=f"Imported from {file.filename}"
    )
    db.add(db_strategy)
    db.commit()
    db.refresh(db_strategy)
    
    # For MVP, we'll just create a document record
    # In a full implementation, we would extract criteria from the document
    db_document = models.Document(
        title=file.filename,
        source_type=file.filename.split('.')[-1].lower(),
        content_summary=f"Strategy document for {strategy_name}"
    )
    db.add(db_document)
    db.commit()
    
    # Clean up the temporary file
    os.remove(file_location)
    
    return {
        "strategy_id": db_strategy.id,
        "strategy_name": strategy_name,
        "status": "success",
        "document_id": db_document.id,
        "message": "Strategy document uploaded successfully. Processing criteria extraction."
    }

# Search endpoints
@router.post("/search/", response_model=schemas.SearchResponse)
async def create_search(
    search: schemas.SearchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Create search query record
    db_query = models.SearchQuery(
        query_text=search.query,
        target_entity=search.target_entity
    )
    db.add(db_query)
    
    # Create agent task for search
    db_task = models.AgentTask(
        agent_type="search",
        task_type="web_search",
        status="pending",
        params={"query": search.query, "target_entity": search.target_entity}
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_query)
    db.refresh(db_task)
    
    # Use the wrapper function for the background task
    background_tasks.add_task(run_task_processor, db_task.id)
    
    return {
        "search_id": db_query.id,
        "task_id": db_task.id,
        "status": "pending",
        "message": "Search task submitted and processing initiated."
    }

@router.get("/search/{search_id}/results", response_model=List[schemas.SearchResult])
def get_search_results(search_id: int, db: Session = Depends(get_db)):
    results = db.query(models.SearchResult).filter(models.SearchResult.query_id == search_id).all()
    return results

# Endpoint to trigger crawling for unprocessed search results
@router.post("/tasks/crawl-search-results/{search_id}", status_code=202)
async def trigger_crawl_tasks_for_search(
    search_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Finds unprocessed search results for a given search_id and creates crawl tasks."""
    # Find the original search query
    search_query = db.query(models.SearchQuery).filter(models.SearchQuery.id == search_id).first()
    if not search_query:
        raise HTTPException(status_code=404, detail=f"Search query with ID {search_id} not found.")
        
    # Find unprocessed search results for this query
    unprocessed_results = db.query(models.SearchResult).filter(
        models.SearchResult.query_id == search_id,
        models.SearchResult.is_processed == False
    ).all()
    
    if not unprocessed_results:
        return {"message": f"No unprocessed search results found for search ID {search_id} to crawl."}
        
    tasks_created_count = 0
    for result in unprocessed_results:
        # Create a new task for the WebCrawlerAgent
        db_task = models.AgentTask(
            agent_type="web_crawler",
            task_type="crawl_url",
            status="pending",
            # Pass URL and the specific SearchResult ID for later updating
            params={"url": result.url, "search_result_id": result.id} 
        )
        db.add(db_task)
        db.commit() # Commit each task individually to get ID immediately
        db.refresh(db_task)
        
        # Schedule the task for processing
        background_tasks.add_task(run_task_processor, db_task.id)
        tasks_created_count += 1
        
    return {
        "message": f"Created and initiated {tasks_created_count} crawl tasks for search ID {search_id}.",
        "tasks_created_count": tasks_created_count
    }

# Endpoint to trigger information extraction for a completed crawl task
@router.post("/tasks/extract-from-crawl/{crawl_task_id}", status_code=202)
async def trigger_extraction_task_for_crawl(
    crawl_task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Finds a completed crawl task and triggers an extraction task based on its content."""
    # Fetch the completed crawl task
    crawl_task = db.query(models.AgentTask).filter(
        models.AgentTask.id == crawl_task_id,
        models.AgentTask.agent_type == "web_crawler",
        models.AgentTask.task_type == "crawl_url"
    ).first()
    
    if not crawl_task:
        raise HTTPException(status_code=404, detail=f"Web crawl task with ID {crawl_task_id} not found.")
        
    if crawl_task.status != "completed":
         raise HTTPException(status_code=400, detail=f"Crawl task {crawl_task_id} is not completed (status: {crawl_task.status}).")

    if not crawl_task.result or crawl_task.result.get('status') != 'success':
        return {"message": f"Crawl task {crawl_task_id} did not complete successfully or has no result content. Skipping extraction."}

    # Extract necessary info from the crawl task's result
    # Adjust keys based on what WebCrawlerAgent.crawl_url actually returns
    content_snippet = crawl_task.result.get("extracted_content_snippet") # Or potentially full content if stored
    source_url = crawl_task.result.get("url")
    original_search_result_id = crawl_task.params.get("search_result_id") # Get original link if needed
    
    # Check if content is usable
    if not content_snippet: # Check for snippet or full content depending on implementation
         return {"message": f"No content found in result of crawl task {crawl_task_id}. Skipping extraction."}

    # Create a new task for the InformationExtractionAgent
    db_task = models.AgentTask(
        agent_type="information_extraction",
        task_type="extract_from_content", # Matches the type handled by the agent
        status="pending",
        # Pass the content and source URL
        params={
            "content": content_snippet, # Pass the snippet (or full content if available/stored)
            "source_url": source_url,
            "original_search_result_id": original_search_result_id # Pass along if needed later
        } 
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # Schedule the extraction task
    background_tasks.add_task(run_task_processor, db_task.id)
    
    return {
        "message": f"Created and initiated information extraction task {db_task.id} based on crawl task {crawl_task_id}.",
        "extraction_task_id": db_task.id
    }

# Analysis endpoints
@router.post("/analysis/", response_model=schemas.AnalysisResponse)
async def create_analysis(
    analysis: schemas.AnalysisCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Validate strategy exists
    db_strategy = db.query(models.InvestmentStrategy).filter(models.InvestmentStrategy.id == analysis.strategy_id).first()
    if db_strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Create agent task for analysis
    db_task = models.AgentTask(
        agent_type="analysis",
        task_type="company_analysis",
        status="pending",
        params={
            "strategy_id": analysis.strategy_id,
            "filters": analysis.filters if analysis.filters else {}
        }
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # Use the wrapper function for the background task
    background_tasks.add_task(run_task_processor, db_task.id)

    return {
        "task_id": db_task.id,
        "status": "pending",
        "message": "Analysis task submitted and processing initiated."
    }

@router.get("/analysis/results/{strategy_id}", response_model=List[schemas.AnalysisResult])
def get_analysis_results(strategy_id: int, db: Session = Depends(get_db)):
    # Simply fetch and return existing results for the strategy ID
    results = db.query(models.AnalysisResult).filter(models.AnalysisResult.strategy_id == strategy_id).all()
    
    return results

# New endpoint to delete analysis results for a specific strategy
@router.delete("/analysis/results/{strategy_id}", status_code=200)
def delete_analysis_results(strategy_id: int, db: Session = Depends(get_db)):
    """Deletes all analysis results associated with a specific strategy ID."""
    # Query for the results to be deleted
    results_to_delete = db.query(models.AnalysisResult).filter(
        models.AnalysisResult.strategy_id == strategy_id
    ).all()
    
    count = len(results_to_delete)
    
    if count == 0:
        return {"message": f"No analysis results found for strategy ID {strategy_id} to delete."}
    
    # Delete each result
    for result in results_to_delete:
        db.delete(result)
    
    # Commit the transaction
    db.commit()
    
    return {"message": f"Successfully deleted {count} analysis results for strategy ID {strategy_id}."}

# Agent task status endpoints
@router.get("/tasks/{task_id}", response_model=schemas.AgentTask)
def get_task_status(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks/", response_model=List[schemas.AgentTask])
def get_tasks(
    agent_type: Optional[str] = None, 
    status: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    query = db.query(models.AgentTask)
    
    if agent_type:
        query = query.filter(models.AgentTask.agent_type == agent_type)
    
    if status:
        query = query.filter(models.AgentTask.status == status)
    
    tasks = query.offset(skip).limit(limit).all()
    return tasks

# New endpoint to delete a specific agent task
@router.delete("/tasks/{task_id}", status_code=200)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Deletes a specific agent task by its ID."""
    task_to_delete = db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
    
    if not task_to_delete:
        raise HTTPException(status_code=404, detail=f"Agent task with ID {task_id} not found.")
        
    task_info = f"Task ID {task_id} (Type: {task_to_delete.agent_type}/{task_to_delete.task_type}, Status: {task_to_delete.status})"
    
    db.delete(task_to_delete)
    db.commit()
    
    return {"message": f"Successfully deleted task: {task_info}"}

# Make sure the main app includes this router if it's defined separately
# from fastapi import FastAPI
# app = FastAPI()
# app.include_router(router, prefix="/api") # Example
