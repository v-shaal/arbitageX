"""
Enhanced ArbitrageX Agent System using LlamaIndex for orchestration
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from tavily import TavilyClient # Import TavilyClient
import requests # Import requests
from bs4 import BeautifulSoup # Import BeautifulSoup

# Load environment variables BEFORE LlamaIndex imports
load_dotenv()

import chromadb # Import chromadb
from llama_index.core import Settings, VectorStoreIndex, Document, StorageContext # Import StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore # Import ChromaVectorStore
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.llms.gemini import Gemini  # Import Gemini LLM
from llama_index.embeddings.gemini import GeminiEmbedding # Import Gemini Embedding
from llama_index.core.node_parser import SentenceSplitter

# Fetch API key from environment
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

# Configure LlamaIndex settings with Gemini
Settings.llm = Gemini(api_key=google_api_key, model_name="models/gemini-2.5-pro-preview-03-25") # Or your preferred Gemini model
Settings.embed_model = GeminiEmbedding(api_key=google_api_key, model_name="models/embedding-001") # Default Gemini embedding model
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)

class LlamaIndexOrchestrator:
    """
    Enhanced orchestrator using LlamaIndex for agent coordination and document processing
    """
    
    def __init__(self, db_session):
        """Initialize the LlamaIndex orchestrator"""
        self.db = db_session
        
        # Initialize ChromaDB client and collection
        # Ensure ./chroma_db_data directory exists or is created
        chroma_path = os.path.join(os.getcwd(), "chroma_db_data") 
        os.makedirs(chroma_path, exist_ok=True) 
        db_chroma = chromadb.PersistentClient(path=chroma_path)
        chroma_collection = db_chroma.get_or_create_collection("arbitragex_documents")
        
        # Create vector store and storage context
        self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Load or build the index from the vector store
        self.index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            storage_context=self.storage_context,
            # embed_model is automatically picked from Settings
        )

        # Initialize the agent
        self.agent = self._create_agent()
        
    def _create_agent(self):
        """Create a ReAct agent with tools for different tasks"""
        tools = [
            FunctionTool.from_defaults(
                name="search_web",
                fn=self.search_web,
                description="Search the web for information about companies"
            ),
            FunctionTool.from_defaults(
                name="crawl_url",
                fn=self.crawl_url,
                description="Extract content from a specific URL"
            ),
            FunctionTool.from_defaults(
                name="extract_information",
                fn=self.extract_information,
                description="Extract structured information from text"
            ),
            FunctionTool.from_defaults(
                name="process_csv",
                fn=self.process_csv,
                description="Process company data from CSV files"
            ),
            FunctionTool.from_defaults(
                name="score_company",
                fn=self.score_company,
                description="Score a company against investment criteria"
            ),
            FunctionTool.from_defaults(
                name="store_document_vectors",
                fn=self.store_document_vectors,
                description="Store document vectors in the vector database"
            )
        ]
        
        return ReActAgent.from_tools(tools, verbose=True)
    
    async def execute_task(self, task_type, params):
        """Execute a task using the LlamaIndex agent"""
        try:
            # Convert task to a natural language query for the agent
            query = self._task_to_query(task_type, params)
            
            # Execute the query using the agent
            response = await self.agent.aquery(query)
            
            # Process and return the response
            return {
                "status": "success",
                "result": response.response,
                "task_type": task_type,
                "completed_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logging.error(f"Error executing task: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "task_type": task_type,
                "completed_at": datetime.utcnow().isoformat()
            }
    
    def _task_to_query(self, task_type, params):
        """Convert a task type and parameters to a natural language query"""
        if task_type == "web_search":
            return f"Search for companies matching these criteria: {params.get('query')}"
        elif task_type == "crawl_url":
            return f"Extract content from this URL: {params.get('url')}"
        elif task_type == "extract_information":
            return f"Extract key information from this content about companies, their financials, and events"
        elif task_type == "process_csv":
            return f"Process this CSV file with company data using the mapping: {params.get('mapping')}"
        elif task_type == "company_analysis":
            return f"Analyze company with ID {params.get('company_id')} against strategy with ID {params.get('strategy_id')}"
        elif task_type == "store_vectors":
            return f"Store vector embeddings for document with ID {params.get('document_id')}"
        else:
            return f"Execute task of type {task_type} with parameters {params}"
    
    # Tool implementation methods
    async def search_web(self, query: str) -> Dict[str, Any]:
        """Search the web for information about companies using Tavily"""
        logging.info(f"Searching web for: {query} using Tavily")
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            logging.error("TAVILY_API_KEY environment variable not set.")
            return {"status": "error", "error": "Tavily API key not configured."}
            
        try:
            client = TavilyClient(api_key=tavily_api_key)
            # Using basic search, consider search_depth="advanced" if needed
            response = await client.search(query=query, search_depth="basic", max_results=7)
            
            # Format results to match expected structure
            formatted_results = [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "") # Tavily uses 'content' for snippet
                }
                for result in response.get("results", [])
            ]
            
            return {
                "status": "success",
                "results": formatted_results
            }
        except Exception as e:
            logging.error(f"Error during Tavily search: {e}")
            return {"status": "error", "error": str(e)}
    
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """Extract content from a specific URL using requests and BeautifulSoup"""
        logging.info(f"Crawling URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10) # Added timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Basic text extraction (remove script/style, get text)
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose() # Remove these tags
            
            text_content = soup.get_text(separator=' \n', strip=True)
            
            # Optional: Create/Update Document entry in SQL DB here
            # document_id = create_or_update_document(self.db, url, text_content)
            document_id = hash(url) # Placeholder ID for now

            return {
                "status": "success",
                "content": text_content,
                "document_id": document_id 
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error crawling URL {url}: {e}")
            return {"status": "error", "error": f"Request failed: {e}"}
        except Exception as e:
            logging.error(f"Error parsing content from {url}: {e}")
            return {"status": "error", "error": f"Parsing failed: {e}"}
    
    async def extract_information(self, text: str) -> Dict[str, Any]:
        """Extract structured information from text using Gemini"""
        logging.info(f"Extracting information from text (first 100 chars): {text[:100]}...")
        
        prompt_template = f"""
Please extract the following information from the text provided below. 
Present the output as a JSON object with the keys 'company_name', 'financial_metrics' (containing 'revenue', 'growth_rate', 'ebitda', 'employee_count'), and 'events' (a list of objects with 'event_type', 'date', 'amount', 'entity'). 
If a piece of information is not found, represent it as null or an empty list/object as appropriate.

Text:
{text}

JSON Output:
"""

        
        response_text = "" # Initialize response_text
        try:
            # Use the globally configured LLM (Gemini)
            response = await Settings.llm.acomplete(prompt_template)
            response_text = response.text.strip()
            
            # Attempt to parse the JSON response from the LLM
            # Remove potential markdown code blocks
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            extracted_data = json.loads(response_text)
            
            # Basic validation (can be expanded)
            if not isinstance(extracted_data, dict):
                raise ValueError("LLM response was not a valid JSON object.")
            
            logging.info(f"Successfully extracted data: {extracted_data}")
            return {
                "status": "success",
                "extracted_data": extracted_data
            }
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response from LLM: {e}\nResponse: {response_text}")
            return {"status": "error", "error": f"LLM response was not valid JSON: {e}"}
        except Exception as e:
            logging.error(f"Error during information extraction: {e}")
            return {"status": "error", "error": str(e)}
    
    async def process_csv(self, file_path: str, mapping: Dict[str, str]) -> Dict[str, Any]:
        """Process company data from CSV files"""
        # Mock implementation for MVP
        logging.info(f"Processing CSV file: {file_path} with mapping: {mapping}")
        return {
            "status": "success",
            "companies_processed": 10,
            "companies_created": 8
        }
    
    async def score_company(self, company_id: int, strategy_id: int) -> Dict[str, Any]:
        """Score a company against investment criteria"""
        # Mock implementation for MVP
        logging.info(f"Scoring company {company_id} against strategy {strategy_id}")
        return {
            "status": "success",
            "overall_score": 85,
            "score_breakdown": {
                "industry_match": 90,
                "revenue_match": 80,
                "growth_match": 95,
                "location_match": 70
            },
            "explanation": "This company is a strong match for the investment strategy due to its high growth rate and industry alignment."
        }
    
    async def store_document_vectors(self, document_id: int, text_content: str) -> Dict[str, Any]:
        """Store document vectors in the persistent vector database"""
        try:
            # Create documents
            documents = [Document(text=text_content, metadata={"document_id": str(document_id)})] # Ensure metadata keys/values are strings if needed by Chroma
            # Parse nodes using global Settings
            nodes = Settings.node_parser.get_nodes_from_documents(documents)
            # Insert nodes into the index (which uses the persistent Chroma store)
            self.index.insert_nodes(nodes)
            # Persist changes (Chroma client handles this automatically with PersistentClient)
            # db_chroma.persist() # Not needed with PersistentClient
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunk_count": len(nodes)
            }
        except Exception as e:
            logging.error(f"Error storing document vectors for doc {document_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def query_vector_store(self, query: str, document_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Query the persistent vector store for relevant information"""
        try:
            query_engine = self.index.as_query_engine()
            # Add filtering here if needed based on document_ids or other metadata
            # Example (requires metadata filtering setup in query engine or vector store):
            # if document_ids:
            #     query_engine = self.index.as_query_engine(filters=MetadataFilters(...))
            
            response = query_engine.query(query)
            
            # Process response nodes if needed to extract metadata/scores
            results = []
            for node_with_score in response.source_nodes:
                results.append({
                    "document_id": node_with_score.node.metadata.get("document_id", "N/A"),
                    "response_chunk": node_with_score.node.get_content(),
                    "relevance_score": node_with_score.score
                })

            return {
                "status": "success",
                "results": results, 
                "query": query,
                "summary_response": response.response # Agent's summarized response
            }
        except Exception as e:
             logging.error(f"Error querying vector store: {e}")
             return {"status": "error", "error": str(e)}

# Agent implementations using LlamaIndex orchestrator
class DataIngestionAgent:
    """Agent for data ingestion tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def process_csv(self, params):
        """Process a CSV file with company data"""
        return await self.orchestrator.execute_task("process_csv", params)
    
    async def process_strategy_document(self, params):
        """Process a strategy document"""
        # First store the document
        store_result = await self.orchestrator.store_document_vectors(
            params.get("document_id", 0),
            params.get("content", "")
        )
        
        # Then extract criteria
        extract_result = await self.orchestrator.extract_information(params.get("content", ""))
        
        return {
            "status": "success",
            "store_result": store_result,
            "extract_result": extract_result
        }

class SearchAgent:
    """Agent for search tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def web_search(self, params):
        """Perform a web search"""
        return await self.orchestrator.execute_task("web_search", params)

class WebCrawlerAgent:
    """Agent for web crawling tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def crawl_url(self, params):
        """Crawl a URL and extract content"""
        return await self.orchestrator.execute_task("crawl_url", params)

class InformationExtractionAgent:
    """Agent for information extraction tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def extract_information(self, params):
        """Extract information from text"""
        return await self.orchestrator.execute_task("extract_information", params)

class AnalysisAgent:
    """Agent for analysis tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def analyze_companies(self, params):
        """Analyze companies against a strategy"""
        return await self.orchestrator.execute_task("company_analysis", params)

class StorageAgent:
    """Agent for storage tasks"""
    
    def __init__(self, db_session, orchestrator=None):
        self.db = db_session
        self.orchestrator = orchestrator or LlamaIndexOrchestrator(db_session)
    
    async def store_document_vectors(self, params):
        """Store document vectors"""
        return await self.orchestrator.execute_task("store_vectors", params)
    
    async def query_vectors(self, params):
        """Query vector store"""
        return await self.orchestrator.query_vector_store(
            params.get("query", ""),
            params.get("document_ids", None)
        )

# Main orchestrator agent that coordinates all other agents
class OrchestratorAgent:
    """Main orchestrator agent that coordinates all other agents"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.orchestrator = LlamaIndexOrchestrator(db_session)
        
        # Initialize all agent types
        self.data_ingestion_agent = DataIngestionAgent(db_session, self.orchestrator)
        self.search_agent = SearchAgent(db_session, self.orchestrator)
        self.web_crawler_agent = WebCrawlerAgent(db_session, self.orchestrator)
        self.information_extraction_agent = InformationExtractionAgent(db_session, self.orchestrator)
        self.analysis_agent = AnalysisAgent(db_session, self.orchestrator)
        self.storage_agent = StorageAgent(db_session, self.orchestrator)
    
    async def create_task(self, agent_type, task_type, params):
        """Create and execute a task using the appropriate agent"""
        # Update task status in database
        from backend.models import AgentTask
        
        task = AgentTask(
            agent_type=agent_type,
            task_type=task_type,
            status="pending",
            params=params,
            created_at=datetime.utcnow()
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        # Update task to running
        task.status = "running"
        task.started_at = datetime.utcnow()
        self.db.commit()
        
        try:
            # Execute task with appropriate agent
            result = await self._execute_agent_task(agent_type, task_type, params)
            
            # Update task with result
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.utcnow()
            self.db.commit()
            
            return task.id
        except Exception as e:
            # Update task with error
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            self.db.commit()
            
            raise e
    
    async def _execute_agent_task(self, agent_type, task_type, params):
        """Execute a task using the appropriate agent"""
        if agent_type == "data_ingestion":
            if task_type == "process_csv":
                return await self.data_ingestion_agent.process_csv(params)
            elif task_type == "process_strategy_document":
                return await self.data_ingestion_agent.process_strategy_document(params)
        
        elif agent_type == "search":
            if task_type == "web_search":
                return await self.search_agent.web_search(params)
        
        elif agent_type == "web_crawler":
            if task_type == "crawl_url":
                return await self.web_crawler_agent.crawl_url(params)
        
        elif agent_type == "information_extraction":
            if task_type == "extract_information":
                return await self.information_extraction_agent.extract_information(params)
        
        elif agent_type == "analysis":
            if task_type == "company_analysis":
                return await self.analysis_agent.analyze_companies(params)
        
        elif agent_type == "storage":
            if task_type == "store_document_vectors":
                return await self.storage_agent.store_document_vectors(params)
            elif task_type == "query_vectors":
                return await self.storage_agent.query_vectors(params)
        
        raise ValueError(f"Unknown agent type '{agent_type}' or task type '{task_type}'")
