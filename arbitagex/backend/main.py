from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd
import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from . import models, schemas
from .database import engine, get_db, SessionLocal
from .agents import OrchestratorAgent

# Create database tables
models.Base.metadata.create_all(bind=engine)

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
def read_companies(
    skip: int = 0, 
    limit: int = 100, 
    name: Optional[str] = None, # Add name query parameter
    db: Session = Depends(get_db)
):
    query = db.query(models.Company).filter(
        ~models.Company.name.startswith("Test Company")
    )
    # Apply name filter if provided (case-insensitive partial match)
    if name:
        query = query.filter(models.Company.name.ilike(f"%{name}%"))
        
    companies = query.offset(skip).limit(limit).all()
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

# Endpoint to manually trigger processing for a specific pending task
@router.post("/tasks/{task_id}/process", status_code=202)
async def trigger_specific_task_processing(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually triggers the background processing for a specific task ID."""
    # Find the task
    task = db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task ID {task_id} not found.")
        
    # Optional: Check if task is already running/completed/failed
    if task.status != "pending":
        return {"message": f"Task {task_id} is not pending (status: {task.status}). Processing not re-initiated."}

    # Schedule the task using the existing background processor
    background_tasks.add_task(run_task_processor, task.id)
    
    return {"message": f"Processing manually triggered for task ID {task_id}. Monitor its status."}

# Endpoint to trigger overview generation and storage for a company
# Modified to create a master orchestration task
@router.post("/companies/{company_id}/update-overview", status_code=202)
async def trigger_company_profile_update(
    company_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Creates a master task to generate a full profile (overview, links, financials) for a company."""
    # 1. Find Company
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company ID {company_id} not found.")

    # 2. Create the master orchestration task
    db_task = models.AgentTask(
        # Define a new agent type or use a general 'orchestration' type
        agent_type="orchestration", 
        task_type="generate_full_profile",
        status="pending",
        # Pass the company ID and name needed to start the process
        params={"company_id": company_id, "company_name": company.name} 
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # 3. Schedule the master task using the background processor
    background_tasks.add_task(run_task_processor, db_task.id)
    
    return {
        "message": f"Master task created to generate full profile for Company ID {company_id}. Monitor task status.",
        "master_task_id": db_task.id
    }

# Endpoint to trigger searching and storing source links for a company
# NOTE: This update-links endpoint should ideally also become part of the 
# 'generate_full_profile' orchestration task rather than being separate.
# We will leave it for now but recommend merging its goal into the main profile task.
@router.post("/companies/{company_id}/update-links", status_code=202)
async def update_company_links(
    company_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Triggers tasks to search for company links (website, linkedin etc.) and store them."""
    # 1. Find Company
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company ID {company_id} not found.")

    # 2. Create Search Task (Example: Search for official website and LinkedIn)
    search_query_text = f"{company.name} official website linkedin profile"
    search_task = models.AgentTask(
        agent_type="search",
        task_type="web_search",
        status="pending",
        params={"query": search_query_text, "target_entity": company.name, "max_results": 3}
    )
    db.add(search_task)
    db.commit()
    db.refresh(search_task)
    background_tasks.add_task(run_task_processor, search_task.id)
    
    # --- How to link Search Results back to Link Storage? ---
    # This is complex. Current setup doesn't automatically chain:
    # Search -> Crawl -> Extract Link Type -> Store Link
    # For MVP, we'll *simulate* finding links and create a direct storage task.
    # In reality, this needs better orchestration.
    
    # --- Simulation: Assume search/crawl/extract found these links ---
    simulated_links = [
        {"url": f"https://{company.name.lower().replace(' ', '')}.com", "link_type": "website", "description": "Simulated Official Website"},
        {"url": f"https://linkedin.com/company/{company.name.lower().replace(' ', '-')}", "link_type": "linkedin", "description": "Simulated LinkedIn Profile"}
    ]
    if company.website: # Add existing website if present
         if not any(l['url'] == company.website for l in simulated_links):
              simulated_links.append({"url": company.website, "link_type": "website", "description": "Existing Website"})
    # -----------------------------------------------------------------

    # 3. Create Task to Store the (Simulated) Links
    # Use overwrite=True to replace previous links found by this process
    link_storage_task = models.AgentTask(
        agent_type="storage",
        task_type="store_company_links",
        status="pending",
        params={"company_id": company_id, "links": simulated_links, "overwrite": True} 
    )
    db.add(link_storage_task)
    db.commit()
    db.refresh(link_storage_task)
    background_tasks.add_task(run_task_processor, link_storage_task.id)

    return {
        "message": f"Tasks created to find and store links for Company ID {company_id}. Check task statuses.",
        "search_task_id": search_task.id,
        "link_storage_task_id": link_storage_task.id
    }

# Endpoint to trigger storage of aggregated extracted data for a company
@router.post("/tasks/store-aggregated-data/{company_id}", status_code=202)
async def trigger_storage_for_company(
    company_id: int,
    aggregated_data: List[Dict[str, Any]], # Expect a list of extracted_data dicts
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Receives aggregated extracted data and triggers various storage agent tasks."""
    # 1. Find Company (optional check)
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company ID {company_id} not found.")
        
    if not aggregated_data:
         return {"message": "No aggregated data provided. Nothing to store."}
         
    # --- Trigger Storage Tasks --- 
    storage_task_ids = []
    overview_to_store = None
    links_to_store = []
    metrics_events_payloads = [] # Store payloads for store_extracted_data
    
    # Consolidate data
    for data_item in aggregated_data:
        # Prepare payload for metrics/events storage
        metrics_events_payloads.append({
            "company_id": company_id,
            "extracted_data": data_item, # Pass the whole item 
            "source_url": data_item.get("source_url", "Unknown") 
        })
        
        # Find the best summary/overview (e.g., from the first source)
        if not overview_to_store and data_item.get("summary"): 
            overview_to_store = data_item.get("summary")
            
        # Collect potential links (Refine this logic as needed)
        source_url = data_item.get("source_url")
        if source_url:
             link_type = "other" # Default
             if "linkedin.com" in source_url: link_type = "linkedin"
             # Add logic to detect website based on company name if needed
             links_to_store.append({"url": source_url, "link_type": link_type, "description": f"Source: {data_item.get('company_name_mentioned', 'Extracted Data')}"})
    
    # Create task for storing Metrics & Events (can be one task per source)
    for payload in metrics_events_payloads:
        db_task_metrics_events = models.AgentTask(
            agent_type="storage",
            task_type="store_extracted_data",
            status="pending",
            params=payload 
        )
        db.add(db_task_metrics_events)
        db.commit()
        db.refresh(db_task_metrics_events)
        background_tasks.add_task(run_task_processor, db_task_metrics_events.id)
        storage_task_ids.append(db_task_metrics_events.id)

    # Create task for storing Overview (if found)
    if overview_to_store:
        db_task_overview = models.AgentTask(
            agent_type="storage",
            task_type="store_company_overview",
            status="pending",
            params={"company_id": company_id, "overview": overview_to_store}
        )
        db.add(db_task_overview)
        db.commit()
        db.refresh(db_task_overview)
        background_tasks.add_task(run_task_processor, db_task_overview.id)
        storage_task_ids.append(db_task_overview.id)
        
    # Create task for storing Links (if any found)
    if links_to_store:
        db_task_links = models.AgentTask(
            agent_type="storage",
            task_type="store_company_links",
            status="pending",
            # Use overwrite=False by default to avoid deleting manually added links?
            # Or maybe filter links_to_store for uniqueness before saving.
            params={"company_id": company_id, "links": links_to_store, "overwrite": False} 
        )
        db.add(db_task_links)
        db.commit()
        db.refresh(db_task_links)
        background_tasks.add_task(run_task_processor, db_task_links.id)
        storage_task_ids.append(db_task_links.id)
        
    return {
        "message": f"Triggered {len(storage_task_ids)} storage sub-tasks for Company ID {company_id}.",
        "storage_task_ids": storage_task_ids
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
