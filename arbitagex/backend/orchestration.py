# arbitagex/backend/orchestration.py

import logging
import os
import time
import requests
import json
from typing import List, Dict, Any, Type, Optional

from langchain.agents import AgentExecutor, create_react_agent # Example agent type
from langchain_core.tools import BaseTool, ToolException
from langchain_core.prompts import PromptTemplate # Or specific agent prompt
from langchain_core.language_models import BaseLanguageModel
# Import Langchain's wrapper for Google models
from langchain_google_genai import ChatGoogleGenerativeAI

# Import LlamaIndex Settings to access the globally configured LLM
from llama_index.core import Settings

# Local imports (might need adjustments based on final structure)
# from . import models, schemas # If directly accessing DB models/schemas
# from .database import SessionLocal # If needing direct DB access

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Ensure logging is configured

# --- Constants --- 
# TODO: Move configuration to a central place or pass it in
BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8080/api")
POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 12 # 12 * 5s = 60 seconds

# --- Custom Langchain Tools ---

class SearchCompanyTool(BaseTool):
    name: str = "search_company_information"
    description: str = "Initiates a background search task for a company name, polls for completion, and returns a dictionary containing a list of relevant URLs found and the associated search_query_id."
    # args_schema: Type[BaseModel] = ... # Define input schema if needed

    def _run(self, company_name: str, run_manager=None) -> Dict[str, Any]:
        """Use the tool."""
        logger.info(f"SearchCompanyTool executing for: {company_name}")
        search_task_id = None
        search_query_id = None
        
        # 1. Trigger backend search task
        try:
            create_search_url = f"{BACKEND_API_BASE_URL}/search/"
            payload = {"query": company_name, "target_entity": company_name}
            logger.info(f"Calling POST {create_search_url}")
            response = requests.post(create_search_url, json=payload, timeout=15)
            response.raise_for_status()
            search_response_data = response.json()
            search_task_id = search_response_data.get("task_id")
            # search_id from the response corresponds to the search_query record ID
            search_query_id = search_response_data.get("search_id") 
            
            if not search_task_id or not search_query_id:
                raise ToolException(f"Failed to initiate search: API response missing task_id or search_id. Response: {search_response_data}")
            logger.info(f"Search task created (Task ID: {search_task_id}, Search Query ID: {search_query_id})")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed during search task creation: {e}")
            raise ToolException(f"Failed to initiate search for {company_name}: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error during search task creation: {e}")
             raise ToolException(f"Unexpected error initiating search: {e}") from e
             
        # 2. Poll backend task status
        task_status_url = f"{BACKEND_API_BASE_URL}/tasks/{search_task_id}"
        logger.info(f"Polling task status at {task_status_url}")
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                time.sleep(POLL_INTERVAL_SECONDS)
                logger.debug(f"Polling attempt {attempt + 1} for task {search_task_id}...")
                response = requests.get(task_status_url, timeout=10)
                response.raise_for_status()
                task_details = response.json()
                status = task_details.get("status")
                
                if status == "completed":
                    logger.info(f"Search task {search_task_id} completed.")
                    # Verify the search_query_id matches if needed
                    # task_result = task_details.get("result", {})
                    # confirmed_search_query_id = task_result.get("search_query_id")
                    # if confirmed_search_query_id != search_query_id:
                    #     logger.warning("Mismatch in search_query_id!")
                    break # Exit polling loop
                elif status == "failed":
                    error_message = task_details.get("error", "Unknown error")
                    logger.error(f"Search task {search_task_id} failed: {error_message}")
                    raise ToolException(f"Backend search task failed: {error_message}")
                elif attempt + 1 == MAX_POLL_ATTEMPTS:
                    logger.error(f"Polling timed out for search task {search_task_id}.")
                    raise ToolException(f"Polling timed out waiting for search task {search_task_id} to complete.")
                # else status is pending or running, continue polling
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API call failed during task polling: {e}")
                # Decide whether to retry or fail the tool
                if attempt + 1 == MAX_POLL_ATTEMPTS:
                     raise ToolException(f"API error during polling: {e}") from e
                # Continue polling after transient error
            except Exception as e:
                 logger.error(f"Unexpected error during task polling: {e}")
                 raise ToolException(f"Unexpected error polling task status: {e}") from e
        
        # 3. Fetch results
        if search_query_id is None:
             # Should not happen if polling succeeded, but as safeguard
             raise ToolException("Could not confirm search_query_id after polling.")
             
        results_url = f"{BACKEND_API_BASE_URL}/search/{search_query_id}/results"
        logger.info(f"Fetching search results from {results_url}")
        try:
            response = requests.get(results_url, timeout=15)
            response.raise_for_status()
            search_results = response.json()
            
            # 4. Extract URLs
            urls = [result.get("url") for result in search_results if result.get("url")]
            logger.info(f"SearchCompanyTool finished. Found {len(urls)} URLs.")
            
            # 5. Return Dict with URLs and search_query_id
            return {
                "urls": urls,
                "search_query_id": search_query_id
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed fetching search results: {e}")
            raise ToolException(f"Failed to fetch search results: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error fetching search results: {e}")
             raise ToolException(f"Unexpected error fetching results: {e}") from e

    async def _arun(self, company_name: str, run_manager=None) -> Dict[str, Any]:
        """Use the tool asynchronously (Not fully implemented - uses sync logic)."""
        logger.warning("SearchCompanyTool._arun is using synchronous logic.")
        # TODO: Implement true async version using httpx and asyncio.sleep
        return self._run(company_name, run_manager)

class CrawlURLsTool(BaseTool):
    name: str = "crawl_website_urls"
    description: str = (
        "Triggers background web crawling tasks for URLs associated with a specific search query ID. "
        "Input should be the search_query_id (integer). "
        "Polls for crawl task completion and returns a list of the task IDs (integer) for successfully completed crawls."
    )

    # Update return type annotation to List[int]
    def _run(self, search_query_id: int, run_manager=None) -> List[int]:
        """Use the tool. Input is the search_query_id."""
        logger.info(f"CrawlURLsTool executing for search_query_id: {search_query_id}")
        crawl_task_ids = []
        
        # 1. Trigger backend crawl tasks
        trigger_url = f"{BACKEND_API_BASE_URL}/tasks/crawl-search-results/{search_query_id}"
        try:
            logger.info(f"Calling POST {trigger_url}")
            response = requests.post(trigger_url, timeout=15)
            response.raise_for_status()
            trigger_response_data = response.json()
            tasks_created_count = trigger_response_data.get("tasks_created_count", 0)
            
            if tasks_created_count == 0:
                 logger.warning(f"No crawl tasks triggered for search_query_id {search_query_id} (maybe no unprocessed results?).")
                 return [] # Return empty if no tasks created
                 
            logger.info(f"Triggered {tasks_created_count} crawl tasks for search_query_id {search_query_id}. Now finding task IDs...")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed triggering crawl tasks: {e}")
            raise ToolException(f"Failed to trigger crawl tasks for search_query_id {search_query_id}: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error triggering crawl tasks: {e}")
             raise ToolException(f"Unexpected error triggering crawl tasks: {e}") from e

        # 2. Find the IDs of the created crawl tasks (Fragile - assumes recent tasks)
        # A better approach would be if the trigger endpoint returned the created task IDs.
        try:
            time.sleep(2) # Short delay to allow tasks to appear in list
            list_tasks_url = f"{BACKEND_API_BASE_URL}/tasks/"
            list_params = {"agent_type": "web_crawler", "limit": tasks_created_count * 2} # Get more than needed
            response = requests.get(list_tasks_url, params=list_params, timeout=10)
            response.raise_for_status()
            all_tasks = response.json()
            # Filter tasks potentially related to this search (heuristic based on params)
            # This is still not robust. Ideally backend links tasks.
            # We resort to finding the N most recent web_crawler tasks.
            web_crawler_tasks = [t for t in all_tasks if t.get("agent_type") == "web_crawler"]
            sorted_tasks = sorted(web_crawler_tasks, key=lambda x: x.get('id', 0), reverse=True)
            crawl_task_ids = [task.get('id') for task in sorted_tasks[:tasks_created_count] if task.get('id')]
            logger.info(f"Identified potential crawl task IDs: {crawl_task_ids}")
            if len(crawl_task_ids) != tasks_created_count:
                 logger.warning("Could not reliably identify all created crawl task IDs.")
                 # Proceed with IDs found, but log warning

        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed listing tasks to find crawl IDs: {e}")
            raise ToolException("Failed to find created crawl task IDs.") from e
        except Exception as e:
             logger.error(f"Unexpected error finding crawl task IDs: {e}")
             raise ToolException("Unexpected error finding crawl task IDs.") from e
             
        if not crawl_task_ids:
            logger.error("No crawl task IDs identified. Cannot poll.")
            return []

        # 3. Poll backend task statuses for the identified crawl tasks
        successful_crawl_task_ids = [] # Store IDs of successful crawls
        logger.info(f"Polling status for crawl tasks: {crawl_task_ids}")
        for task_id in crawl_task_ids:
            task_status_url = f"{BACKEND_API_BASE_URL}/tasks/{task_id}"
            logger.info(f"Polling task {task_id}...")
            for attempt in range(MAX_POLL_ATTEMPTS):
                try:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    response = requests.get(task_status_url, timeout=10)
                    response.raise_for_status()
                    task_details = response.json()
                    status = task_details.get("status")
                    
                    if status == "completed":
                        logger.info(f"Crawl task {task_id} completed.")
                        task_result = task_details.get("result", {})
                        if task_result.get("status") == "success":
                            # ** CHANGE: Store ID if successful **
                            successful_crawl_task_ids.append(task_id)
                            logger.info(f" -> Success, content length: {task_result.get('content_length')}")
                        else:
                             logger.warning(f" -> Failed (Result Status: {task_result.get('status', 'unknown')})")
                        break # Move to next task ID
                    elif status == "failed":
                        error_message = task_details.get("error", "Unknown error")
                        logger.error(f"Crawl task {task_id} failed: {error_message}")
                        break # Move to next task ID
                    elif attempt + 1 == MAX_POLL_ATTEMPTS:
                        logger.error(f"Polling timed out for crawl task {task_id}.")
                        break # Move to next task ID
                except requests.exceptions.RequestException as e:
                    logger.error(f"API call failed polling task {task_id}: {e}")
                    if attempt + 1 == MAX_POLL_ATTEMPTS:
                         logger.error(f"Stopping polling for task {task_id} due to API errors.")
                         break
                except Exception as e:
                     logger.error(f"Unexpected error polling task {task_id}: {e}")
                     break
                     
        # 4. Return list of successful crawl task IDs
        logger.info(f"CrawlURLsTool finished. Found {len(successful_crawl_task_ids)} successful crawl task IDs: {successful_crawl_task_ids}")
        return successful_crawl_task_ids

    # Modify _arun similarly if implementing async
    async def _arun(self, search_query_id: int, run_manager=None) -> List[int]: # Update return type
        """Use the tool asynchronously (Not fully implemented - uses sync logic)."""
        logger.warning("CrawlURLsTool._arun is using synchronous logic.")
        return self._run(search_query_id, run_manager)

class ExtractInformationTool(BaseTool):
    name: str = "extract_structured_information"
    description: str = (
        "Triggers background LLM extraction tasks based on a list of successfully completed crawl task IDs. "
        "Input should be a list of crawl_task_ids (integers). "
        "Polls for extraction task completion and returns a list of the structured data dictionaries extracted by the LLM."
    )

    # Update _run signature to accept List[int]
    def _run(self, successful_crawl_task_ids: List[int], run_manager=None) -> List[Dict[str, Any]]:
        """Use the tool. Input is List[crawl_task_id]."""
        if not successful_crawl_task_ids:
            logger.warning("ExtractInformationTool received empty list of crawl task IDs. Skipping extraction.")
            return []
            
        logger.info(f"ExtractInformationTool executing for {len(successful_crawl_task_ids)} successful crawl tasks: {successful_crawl_task_ids}")
        extraction_task_ids: List[int] = []
        crawl_to_extraction_map: Dict[int, int] = {} 
        
        # 1. Trigger backend extraction tasks for each successful crawl task ID
        # No need to fetch content here, the backend endpoint handles that
        for crawl_task_id in successful_crawl_task_ids:
            trigger_url = f"{BACKEND_API_BASE_URL}/tasks/extract-from-crawl/{crawl_task_id}"
            try:
                logger.info(f"Triggering extraction for crawl task {crawl_task_id} via POST {trigger_url}")
                response = requests.post(trigger_url, timeout=15)
                response.raise_for_status()
                trigger_response_data = response.json()
                new_extraction_task_id = trigger_response_data.get("extraction_task_id")
                
                if new_extraction_task_id:
                    extraction_task_ids.append(new_extraction_task_id)
                    crawl_to_extraction_map[crawl_task_id] = new_extraction_task_id
                    logger.info(f" -> Created Extraction Task ID: {new_extraction_task_id}")
                else:
                    logger.warning(f"API response missing extraction_task_id for crawl task {crawl_task_id}. Response: {trigger_response_data}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"API call failed triggering extraction for crawl task {crawl_task_id}: {e}")
            except Exception as e:
                 logger.error(f"Unexpected error triggering extraction for crawl task {crawl_task_id}: {e}")
                 
        if not extraction_task_ids:
            logger.error("Failed to trigger any extraction tasks.")
            return []

        # 2. Poll backend task statuses for all triggered extraction tasks
        aggregated_results: List[Dict[str, Any]] = []
        logger.info(f"Polling status for extraction tasks: {extraction_task_ids}")
        for task_id in extraction_task_ids:
            task_status_url = f"{BACKEND_API_BASE_URL}/tasks/{task_id}"
            logger.info(f"Polling extraction task {task_id}...")
            for attempt in range(MAX_POLL_ATTEMPTS):
                try:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    response = requests.get(task_status_url, timeout=10)
                    response.raise_for_status()
                    task_details = response.json()
                    status = task_details.get("status")
                    
                    if status == "completed":
                        logger.info(f"Extraction task {task_id} completed.")
                        task_result = task_details.get("result", {})
                        if task_result.get("status") == "success":
                            extracted_data = task_result.get("extracted_data", {}) 
                            if extracted_data:
                                 aggregated_results.append(extracted_data)
                                 logger.info(f" -> Success, retrieved extracted data.")
                            else:
                                 logger.warning(f" -> Success, but no extracted_data field in result.")
                        else:
                             logger.warning(f" -> Failed (Result Status: {task_result.get('status', 'unknown')})")
                        break 
                    elif status == "failed":
                        error_message = task_details.get("error", "Unknown error")
                        logger.error(f"Extraction task {task_id} failed: {error_message}")
                        break 
                    elif attempt + 1 == MAX_POLL_ATTEMPTS:
                        logger.error(f"Polling timed out for extraction task {task_id}.")
                        break 
                except requests.exceptions.RequestException as e:
                    logger.error(f"API call failed polling extraction task {task_id}: {e}")
                    if attempt + 1 == MAX_POLL_ATTEMPTS:
                         logger.error(f"Stopping polling for task {task_id} due to API errors.")
                         break
                except Exception as e:
                     logger.error(f"Unexpected error polling extraction task {task_id}: {e}")
                     break
                     
        # 3. Return aggregated list of extracted data dictionaries
        logger.info(f"ExtractInformationTool finished. Aggregated data from {len(aggregated_results)} sources.")
        return aggregated_results
        
    # Update _arun similarly if implementing async
    async def _arun(self, successful_crawl_task_ids: List[int], run_manager=None) -> List[Dict[str, Any]]: # Update input type
        """Use the tool asynchronously (Not fully implemented - uses sync logic)."""
        logger.warning("ExtractInformationTool._arun is using synchronous logic.")
        return self._run(successful_crawl_task_ids, run_manager)

class StoreCompanyDataTool(BaseTool):
    name: str = "store_company_data"
    description: str = (
        "Triggers backend tasks to store aggregated extracted data (metrics, events, summary, links) "
        "persistently for a given company ID. Input requires company_id (integer) and aggregated_data "
        "(a list of dictionaries, where each dictionary is the result from the extraction tool). "
        "Polls storage tasks and returns a final confirmation message."
    )

    # Update input types: company_id and the list of dicts from Extract tool
    def _run(self, company_id: int, aggregated_data: List[Dict[str, Any]], run_manager=None) -> str:
        """Use the tool."""
        if not aggregated_data:
            logger.warning("StoreCompanyDataTool received empty aggregated_data. Nothing to store.")
            return "No data provided to store."
            
        logger.info(f"StoreCompanyDataTool executing for Company ID: {company_id} with data from {len(aggregated_data)} sources.")
        storage_task_ids = []

        # 1. Trigger backend storage tasks via the new endpoint
        trigger_url = f"{BACKEND_API_BASE_URL}/tasks/store-aggregated-data/{company_id}"
        try:
            logger.info(f"Calling POST {trigger_url} to trigger storage tasks.")
            # Pass the aggregated data in the request body
            response = requests.post(trigger_url, json=aggregated_data, timeout=20) 
            response.raise_for_status()
            trigger_response_data = response.json()
            storage_task_ids = trigger_response_data.get("storage_task_ids", [])
            
            if not storage_task_ids:
                logger.warning(f"Backend did not return any storage task IDs for company {company_id}. Data might not be stored.")
                return "Storage tasks could not be initiated."
                 
            logger.info(f"Triggered {len(storage_task_ids)} storage tasks: {storage_task_ids}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed triggering storage tasks: {e}")
            raise ToolException(f"Failed to trigger storage tasks for company {company_id}: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error triggering storage tasks: {e}")
             raise ToolException(f"Unexpected error triggering storage tasks: {e}") from e

        # 2. Poll backend task statuses for all triggered storage tasks
        completed_count = 0
        failed_count = 0
        logger.info(f"Polling status for storage tasks: {storage_task_ids}")
        for task_id in storage_task_ids:
            task_status_url = f"{BACKEND_API_BASE_URL}/tasks/{task_id}"
            logger.info(f"Polling storage task {task_id}...")
            for attempt in range(MAX_POLL_ATTEMPTS):
                try:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    response = requests.get(task_status_url, timeout=10)
                    response.raise_for_status()
                    task_details = response.json()
                    status = task_details.get("status")
                    
                    if status == "completed":
                        logger.info(f"Storage task {task_id} completed.")
                        task_result = task_details.get("result", {})
                        if task_result.get("status") == "success":
                            logger.info(f" -> Success: {task_result.get('message')}")
                            completed_count += 1
                        else:
                             logger.warning(f" -> Failed (Result Status: {task_result.get('status', 'unknown')})")
                             failed_count += 1
                        break 
                    elif status == "failed":
                        error_message = task_details.get("error", "Unknown error")
                        logger.error(f"Storage task {task_id} failed: {error_message}")
                        failed_count += 1
                        break 
                    elif attempt + 1 == MAX_POLL_ATTEMPTS:
                        logger.error(f"Polling timed out for storage task {task_id}.")
                        failed_count += 1 # Count timeout as failure for summary
                        break 
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"API call failed polling storage task {task_id}: {e}")
                    if attempt + 1 == MAX_POLL_ATTEMPTS:
                         logger.error(f"Stopping polling for task {task_id} due to API errors.")
                         failed_count += 1
                         break
                except Exception as e:
                     logger.error(f"Unexpected error polling storage task {task_id}: {e}")
                     failed_count += 1
                     break
                     
        # 3. Return final confirmation message
        result_message = f"""Storage process initiated for Company ID {company_id}. Tasks completed: {completed_count}/{len(storage_task_ids)}. Tasks failed/timed out: {failed_count}.
Please verify data via company details endpoint."""
        logger.info(result_message)
        return result_message
        
    # Update _arun similarly if implementing async
    async def _arun(self, company_id: int, aggregated_data: List[Dict[str, Any]], run_manager=None) -> str:
        """Use the tool asynchronously (Not fully implemented - uses sync logic)."""
        logger.warning("StoreCompanyDataTool._arun is using synchronous logic.")
        # TODO: Implement true async version using httpx and asyncio.sleep
        return self._run(company_id, aggregated_data, run_manager)

# --- Orchestration Agent Setup ---

def get_orchestration_agent_executor(llm: BaseLanguageModel) -> AgentExecutor:
    """Creates and returns the Langchain Agent Executor for orchestration."""
    # Added type hint for clarity
    
    # 1. Instantiate Tools
    tools = [
        SearchCompanyTool(),
        CrawlURLsTool(),
        ExtractInformationTool(),
        StoreCompanyDataTool(),
        # Add GenerateOverviewTool if implemented
    ]

    # 2. Define Prompt Template (Example using ReAct prompt style)
    # You might need to customize this significantly
    # Ensure the prompt clearly defines the goal (generate full profile) and available tools
    prompt = PromptTemplate.from_template("""
    You are an assistant designed to research companies and generate comprehensive profiles.
    Your goal is to gather information about a company, extract key details, and store them.

    TOOLS:
    ------
    You have access to the following tools:
    {tools}

    To use a tool, please use the following format:
    ```
    Thought: Do I need to use a tool? Yes
    Action: The action to take. Should be one of [{tool_names}]
    Action Input: The input to the action
    Observation: The result of the action
    ```

    When you have gathered, extracted, and stored all necessary information, or if you cannot proceed further, you MUST respond with the final answer in the following format:
    ```
    Thought: Do I need to use a tool? No
    Final Answer: [Provide a summary of the process, e.g., "Successfully generated and stored profile for Company X." or "Failed to crawl key sources for Company Y."]
    ```

    Begin!

    Input: {input}
    Thought: {agent_scratchpad}
    """)

    # 3. Get LLM - It's now passed directly as an argument
    if llm is None:
        # This check might be redundant if run_profile_generation ensures it, but good practice
        raise ValueError("LLM instance is required.")
        
    # 4. Create Agent
    # Example using ReAct agent - other types might be suitable too
    agent = create_react_agent(llm, tools, prompt)

    # 5. Create Agent Executor
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    logger.info("Orchestration Agent Executor created.")
    return agent_executor

# --- Main Orchestration Function ---

async def run_profile_generation(company_id: int, company_name: str):
    """Runs the full profile generation workflow for a given company."""
    logger.info(f"Starting profile generation run for Company ID: {company_id}, Name: {company_name}")
    
    # --- Get LLM Instance --- 
    langchain_llm = None
    try:
        # Access the globally configured LlamaIndex LLM
        llama_llm = Settings.llm
        if not llama_llm:
            raise ValueError("LlamaIndex Settings.llm is not configured.")
            
        # Get the model name from the LlamaIndex LLM
        model_name = llama_llm.model # Assumes .model attribute holds the name
        logger.info(f"Retrieved LlamaIndex LLM: {type(llama_llm)}, Model: {model_name}")
        
        # Initialize the Langchain compatible wrapper
        # Ensure GOOGLE_API_KEY environment variable is set
        langchain_llm = ChatGoogleGenerativeAI(model=model_name) 
        logger.info(f"Initialized Langchain LLM wrapper: {type(langchain_llm)}")
        
    except Exception as e:
        logger.error(f"Failed to retrieve/initialize LLM for Langchain: {e}", exc_info=True)
        # TODO: Update central run status tracking (failure)
        return # Stop execution if LLM setup fails
    # --- End LLM Instance --- 
        
    agent_executor = get_orchestration_agent_executor(llm=langchain_llm)
    
    initial_input = f"Generate a comprehensive profile for the company: {company_name} (ID: {company_id}). Search for information, crawl relevant URLs, extract key data (metrics, events, summary), and store the results."
    
    try:
        # Use agent_executor.ainvoke for async execution
        logger.info("Invoking Langchain agent executor...")
        result = await agent_executor.ainvoke({"input": initial_input})
        final_answer = result.get("output", "No final answer provided.")
        logger.info(f"Orchestration run finished for Company ID {company_id}. Final Answer: {final_answer}")
        # TODO: Update central run status tracking (success)
        
    except Exception as e:
        logger.error(f"Error during Langchain agent execution for Company ID {company_id}: {e}", exc_info=True)
        # TODO: Update central run status tracking (failure)

# TODO:
# - Implement the actual logic within the _run/_arun methods of the tools, making necessary API calls.
# - Implement robust polling/waiting logic within tools for backend tasks.
# - Implement proper LLM instance retrieval and potential wrapping for Langchain compatibility.
# - Implement a mechanism to track the status of the overall orchestration run (e.g., using the run_id).
# - Refine the agent prompt.
# - Integrate this run_profile_generation function with the new API endpoint.