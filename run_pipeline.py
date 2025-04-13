import requests
import time
import logging
import json
import sys
from typing import Optional, Dict, Any, List

# --- Configuration ---
BASE_URL = "http://localhost:8080/api"  # Your backend API base URL
COMPANY_NAME = "Embark IT, Inc."      # Company to research
# COMPANY_NAME = "GrowthSoft Inc."  # Example alternative
POLL_INTERVAL_SECONDS = 5             # How often to check task status
MAX_POLL_ATTEMPTS = 24                # Max times to poll (24 * 5s = 120s = 2 mins)
# --- End Configuration ---

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# --- End Logging Setup ---

# --- Helper Functions ---

def make_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Makes an HTTP request, logs details, handles errors, returns JSON response."""
    url = f"{BASE_URL}{endpoint}"
    log_data = f" Data: {json.dumps(data)}" if data else ""
    log_params = f" Params: {params}" if params else ""
    logging.info(f"Triggering: {method} {url}{log_params}{log_data}")

    # Log equivalent curl command (for demonstration)
    curl_data_flag = ""
    if data:
        curl_data_flag = f"-H 'Content-Type: application/json' -d '{json.dumps(data)}'"
    curl_params = ""
    if params:
        curl_params = "?" + "&".join([f"{k}={v}" for k, v in params.items()])

    logging.info(f"Equivalent curl: curl -X {method} {curl_data_flag} '{url}{curl_params}'")

    try:
        response = requests.request(method, url, json=data, params=params, timeout=30) # 30s timeout
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        logging.info(f"Response Status: {response.status_code}")
        if response.content:
            try:
                response_json = response.json()
                logging.info(f"Response JSON: {json.dumps(response_json, indent=2)}")
                return response_json
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON response. Body: {response.text}")
                return None
        else:
            logging.info("Response Body: Empty")
            return None # No content successful response (e.g., DELETE)

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return None

def poll_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Polls a task until completion or failure, or timeout."""
    logging.info(f"--- Polling Task ID: {task_id} ---")
    for attempt in range(MAX_POLL_ATTEMPTS):
        logging.info(f"Polling attempt {attempt + 1}/{MAX_POLL_ATTEMPTS} for task {task_id}...")
        task_details = make_request("GET", f"/tasks/{task_id}")

        if not task_details:
            logging.warning(f"Failed to fetch status for task {task_id}. Retrying...")

        elif task_details.get("status") == "completed":
            logging.info(f"Task {task_id} completed successfully.")
            return task_details

        elif task_details.get("status") == "failed":
            logging.error(f"Task {task_id} failed. Error: {task_details.get('error')}")
            return task_details # Return details even if failed

        elif attempt + 1 == MAX_POLL_ATTEMPTS:
            logging.error(f"Polling timed out for task {task_id} after {MAX_POLL_ATTEMPTS} attempts.")
            return task_details # Return last known details on timeout

        # Wait before the next poll
        time.sleep(POLL_INTERVAL_SECONDS)

    return None # Should be covered by max attempts return, but as fallback

# --- End Helper Functions ---

# --- Main Workflow ---

def run_workflow():
    logging.info(f"--- STARTING WORKFLOW for Company: {COMPANY_NAME} ---")

    # == STEP 1: Find Company ID ==
    logging.info(f"\n--- STEP 1: Find Company ID for '{COMPANY_NAME}' ---")
    logging.info("Description: Using the API to search for the company by name to get its internal ID.")
    company_data_list = make_request("GET", "/companies/", params={"name": COMPANY_NAME})
    company_id = None
    if company_data_list and len(company_data_list) == 1:
        company_id = company_data_list[0].get("id")
        logging.info(f"Found Company ID: {company_id}")
    elif company_data_list and len(company_data_list) > 1:
        company_id = company_data_list[0].get("id")
        logging.warning(f"Found multiple companies matching '{COMPANY_NAME}'. Using the first one (ID: {company_id}).")
    else:
        logging.error(f"Company '{COMPANY_NAME}' not found or API error. Exiting workflow.")
        sys.exit(1) # Exit if company not found

    # == STEP 2: Trigger Master Profile Update Task ==
    logging.info(f"\n--- STEP 2: Trigger Master Profile Update Task for Company ID: {company_id} ---")
    logging.info("Description: Creates a master task that orchestrates the sub-tasks (Search, Crawl, Extract, Store) for profile generation.")
    master_task_response = make_request("POST", f"/companies/{company_id}/update-overview")
    master_task_id = master_task_response.get("master_task_id") if master_task_response else None

    if not master_task_id:
        logging.error("Failed to create master profile update task. Exiting workflow.")
        sys.exit(1)
    logging.info(f"Master Task ID: {master_task_id}")

    # == STEP 3: Poll Master Task & Get Search Task ID ==
    logging.info(f"\n--- STEP 3: Wait for Master Task ({master_task_id}) & Get Search Task ID ---")
    logging.info("Description: The master task's immediate job is just to create the first sub-task (Search). We poll it to get the ID of that Search task.")
    master_task_details = poll_task(master_task_id)
    search_task_id : Optional[int] = None
    search_query_id : Optional[int] = None # Will need this later from Search task result

    if master_task_details and master_task_details.get("status") == "completed" and master_task_details.get("result"):
        search_task_id = master_task_details.get("result", {}).get("search_task_id")
        if search_task_id:
             logging.info(f"Master task created Search Task ID: {search_task_id}")
        else:
             logging.error("Master task completed but did not return a search_task_id in its result. Cannot proceed.")
             sys.exit(1)
    else:
        logging.error(f"Master task {master_task_id} did not complete successfully or result missing. Exiting workflow.")
        sys.exit(1)

    # == STEP 4: Trigger Search Task Processing ==
    logging.info(f"\n--- STEP 4: Manually Trigger Processing for Search Task ID: {search_task_id} ---")
    logging.info("Description: Since the master task only creates the search task record, we manually trigger its processing.")
    trigger_response = make_request("POST", f"/tasks/{search_task_id}/process")
    if not trigger_response:
         logging.warning(f"Failed to get response when triggering search task {search_task_id}. Check logs. Will attempt polling anyway.")
         # Continue assuming it might have been triggered

    # == STEP 5: Poll Search Task Completion & Get Search Query ID ==
    logging.info(f"\n--- STEP 5: Wait for Search Task ({search_task_id}) to Complete ---")
    logging.info("Description: Wait for the Search Agent (using Tavily) to find URLs.")
    search_task_details = poll_task(search_task_id)

    if search_task_details and search_task_details.get("status") == "completed" and search_task_details.get("result"):
        search_query_id = search_task_details.get("result", {}).get("search_query_id")
        results_count = search_task_details.get("result", {}).get("results_stored_count", 0)
        logging.info(f"Search Task completed. Found {results_count} results. Associated Search Query ID: {search_query_id}")
        if not search_query_id:
            logging.error("Search task completed but missing search_query_id in result. Cannot trigger crawling.")
            sys.exit(1)
        if results_count == 0:
            logging.warning("Search task found 0 results. No further crawling or extraction possible for this run.")
            sys.exit(0) # Exit gracefully
    else:
        logging.error(f"Search task {search_task_id} did not complete successfully or result missing. Exiting workflow.")
        sys.exit(1)

    # == STEP 6: Trigger Crawling for Search Results ==
    logging.info(f"\n--- STEP 6: Trigger Crawling for Search Query ID: {search_query_id} ---")
    logging.info("Description: Creates background tasks for the WebCrawlerAgent to visit the URLs found by the search.")
    crawl_trigger_response = make_request("POST", f"/tasks/crawl-search-results/{search_query_id}")
    crawl_tasks_created = crawl_trigger_response.get("tasks_created_count", 0) if crawl_trigger_response else 0

    if crawl_tasks_created == 0:
        logging.error(f"Failed to trigger crawl tasks or no unprocessed results found for search ID {search_query_id}. Exiting.")
        sys.exit(1)
    logging.info(f"Successfully triggered {crawl_tasks_created} crawl tasks.")

    # == STEP 7: Poll Crawl Tasks Completion (Find IDs first) ==
    logging.info(f"\n--- STEP 7: Wait for Crawl Tasks to Complete ---")
    logging.info("Description: Finding the crawl task IDs and waiting for them to finish processing.")
    # LIMITATION: We need to *find* the crawl task IDs. We assume they are the most recent N tasks
    # created with agent_type='web_crawler', where N = crawl_tasks_created. This is fragile.
    logging.warning("Attempting to find crawl task IDs assuming they are the most recent. This might be inaccurate.")
    all_tasks_response = make_request("GET", f"/tasks/", params={"agent_type": "web_crawler", "limit": crawl_tasks_created})
    crawl_task_ids : List[int] = []
    if all_tasks_response:
        # Sort by creation date (newest first) just in case limit doesn't guarantee order
        # Assuming 'id' increments reasonably with creation time for this simple approach
        sorted_tasks = sorted(all_tasks_response, key=lambda x: x.get('id', 0), reverse=True)
        crawl_task_ids = [task.get('id') for task in sorted_tasks[:crawl_tasks_created] if task.get('id')]
        logging.info(f"Identified potential crawl task IDs: {crawl_task_ids}")
    else:
        logging.error("Could not retrieve task list to identify crawl task IDs. Cannot proceed.")
        sys.exit(1)

    successful_crawl_tasks : Dict[int, Dict[str, Any]] = {} # Store details of successful crawls {task_id: task_details}
    for crawl_task_id in crawl_task_ids:
        crawl_task_details = poll_task(crawl_task_id)
        if crawl_task_details and crawl_task_details.get("status") == "completed" and crawl_task_details.get("result", {}).get("status") == "success":
             successful_crawl_tasks[crawl_task_id] = crawl_task_details
             logging.info(f"Crawl task {crawl_task_id} completed successfully.")
        else:
             logging.warning(f"Crawl task {crawl_task_id} did not complete successfully.")

    if not successful_crawl_tasks:
        logging.error("No crawl tasks completed successfully. Cannot proceed to extraction.")
        sys.exit(0) # Exit gracefully

    # == STEP 8: Trigger Extraction for Successful Crawls ==
    logging.info(f"\n--- STEP 8: Trigger Extraction for Successful Crawl Tasks ---")
    logging.info(f"Description: Creating background tasks for the InformationExtractionAgent based on {len(successful_crawl_tasks)} successful crawls.")
    extraction_task_ids : List[int] = []
    for crawl_task_id in successful_crawl_tasks.keys():
        logging.info(f"Triggering extraction based on crawl task {crawl_task_id}...")
        extract_trigger_response = make_request("POST", f"/tasks/extract-from-crawl/{crawl_task_id}")
        if extract_trigger_response and extract_trigger_response.get("extraction_task_id"):
            new_extraction_task_id = extract_trigger_response["extraction_task_id"]
            extraction_task_ids.append(new_extraction_task_id)
            logging.info(f"Created Extraction Task ID: {new_extraction_task_id}")
        else:
            logging.warning(f"Failed to trigger extraction task for crawl task {crawl_task_id}.")

    if not extraction_task_ids:
        logging.error("Failed to create any extraction tasks. Exiting.")
        sys.exit(1)

    # == STEP 9: Poll Extraction Tasks Completion & View Results ==
    logging.info(f"\n--- STEP 9: Wait for Extraction Tasks & View Results ---")
    logging.info("Description: Waiting for the LLM to extract structured data from the crawled content.")
    final_extracted_data : List[Dict[str, Any]] = []
    for extraction_task_id in extraction_task_ids:
        extraction_task_details = poll_task(extraction_task_id)
        if extraction_task_details and extraction_task_details.get("status") == "completed" and extraction_task_details.get("result", {}).get("status") == "success":
            logging.info(f"Extraction Task {extraction_task_id} completed successfully.")
            extracted_data = extraction_task_details.get("result", {}).get("extracted_data", {})
            logging.info(f"Extracted Data (Task {extraction_task_id}): {json.dumps(extracted_data, indent=2)}")
            final_extracted_data.append(extracted_data)
        else:
            logging.warning(f"Extraction task {extraction_task_id} did not complete successfully.")

    # == STEP 10: Next Steps (Manual) ==
    logging.info(f"\n--- STEP 10: Workflow Complete (Extraction Stage) ---")
    logging.info("Description: The script has completed the implemented workflow stages.")
    logging.info(f"Extracted data from {len(final_extracted_data)} sources is available above.")
    logging.info("Next Steps (Manual / Not Implemented in Script):")
    logging.info(" 1. Implement Storage: Create API endpoints and StorageAgent logic to save the extracted data (metrics, events, overview, links) to the database, linking it to the correct company.")
    logging.info(" 2. Trigger Storage: Manually call the storage API endpoints using the extracted data.")
    logging.info(" 3. Verify: Check the company details via API (`GET /api/companies/{company_id}`) or direct database access to confirm updates.")
    logging.info(" 4. UI Integration: Update the frontend UI to display the newly stored overview, financials, news (events), and sources.")

    logging.info("--- WORKFLOW FINISHED ---")


if __name__ == "__main__":
    run_workflow()