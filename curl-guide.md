
Okay, here is a workflow document outlining the sequence of `curl` commands to manually execute the entire profile generation process, from initiation to checking the final results.

**Assumptions:**

*   Your FastAPI backend is running at `http://localhost:8080`.
*   You have `jq` installed for pretty-printing JSON (optional, remove `| jq` if not).
*   You know the `COMPANY_ID` of the company you want to research (e.g., 67 for Embark IT, Inc.).
*   The necessary API endpoints (`/companies/{id}/update-overview`, `/tasks/{id}`, `/tasks/{id}/process`, `/search/{id}/results`, `/tasks/crawl-search-results/{id}`, `/tasks/extract-from-crawl/{id}`, `/tasks/store-aggregated-data/{id}`, `/companies/{id}`) exist and function as implemented previously.

---

## ArbitrageX Backend: Manual Curl Workflow for Company Profile Generation

This document outlines the sequence of `curl` commands required to manually trigger and monitor the full research and update workflow for a specific company profile using the backend API.

**Replace placeholders like `{COMPANY_ID}`, `{MASTER_TASK_ID}`, etc., with the actual IDs obtained during the workflow.**

### Phase 1: Initiation

**Step 1: Trigger Master Profile Generation Task**

*   **Goal:** Start the overall orchestration process for a specific company. This creates a master task record.
*   **Command:**
    ```bash
    # Replace {COMPANY_ID} with the actual ID (e.g., 67)
    curl -X POST http://localhost:8080/api/companies/{COMPANY_ID}/update-overview
    ```
*   **Output:** A JSON response containing the `master_task_id`.
    ```json
    {
      "message": "Master task created to generate full profile for Company ID {COMPANY_ID}. Monitor task status.",
      "master_task_id": 144 # Example ID
    }
    ```
*   **Action:** Note the `master_task_id` (e.g., `144`).

### Phase 2: Search

**Step 2: Poll Master Task & Get Search Task ID**

*   **Goal:** Wait for the master task to run its initial step (creating the search sub-task record) and retrieve the ID of that search sub-task.
*   **Command:**
    ```bash
    # Replace {MASTER_TASK_ID} with the ID from Step 1 (e.g., 144)
    curl -X GET http://localhost:8080/api/tasks/{MASTER_TASK_ID} | jq
    ```
*   **Output:** JSON details of the master task.
*   **Action:** Repeat this command every few seconds until the `"status"` is `"running"` (or potentially "completed" depending on final orchestrator logic). Examine the `"result"` field within the JSON response and note the `search_task_id`.
    ```json
    {
      // ...,
      "status": "running",
      "result": {
        "status": "sub_task_created",
        "message": "Created search task 145. Trigger sub-task processing to continue.",
        "search_task_id": 145 // Example ID
      },
      // ...
    }
    ```
*   **Next:** Proceed once you have the `search_task_id` (e.g., `145`).

**Step 3: Trigger Search Task Processing**

*   **Goal:** Manually schedule the search sub-task (created in the previous step) for execution.
*   **Command:**
    ```bash
    # Replace {SEARCH_TASK_ID} with the ID from Step 2 (e.g., 145)
    curl -X POST http://localhost:8080/api/tasks/{SEARCH_TASK_ID}/process
    ```
*   **Output:** A confirmation message.
    ```json
    {
      "message": "Processing manually triggered for task ID {SEARCH_TASK_ID}. Monitor its status."
    }
    ```
*   **Action:** Proceed to polling the search task.

**Step 4: Poll Search Task Completion & Get Search Query ID**

*   **Goal:** Wait for the Search Agent to run (using Tavily) and confirm completion. Get the `search_query_id` needed to fetch results and trigger crawling.
*   **Command:**
    ```bash
    # Replace {SEARCH_TASK_ID} with the ID from Step 2 (e.g., 145)
    curl -X GET http://localhost:8080/api/tasks/{SEARCH_TASK_ID} | jq
    ```
*   **Output:** JSON details of the search task.
*   **Action:** Repeat this command every few seconds until the `"status"` is `"completed"`. Examine the `"result"` field and note the `search_query_id`.
    ```json
    {
      // ...,
      "status": "completed",
      "result": {
        "status": "success",
        "message": "Search completed. Found 5 results for query: 'Embark IT, Inc.'.",
        "results_stored_count": 5,
        "search_query_id": 34 // Example ID
      },
      // ...
    }
    ```
*   **Next:** Proceed once the task is completed and you have the `search_query_id` (e.g., `34`). If the status becomes `"failed"`, check the `"error"` field and backend logs.

**Step 5: Fetch Search Results (Optional Verification)**

*   **Goal:** View the URLs and snippets found by the search.
*   **Command:**
    ```bash
    # Replace {SEARCH_QUERY_ID} with the ID from Step 4 (e.g., 34)
    curl -X GET http://localhost:8080/api/search/{SEARCH_QUERY_ID}/results | jq
    ```
*   **Output:** JSON array of search result objects.
*   **Action:** Review the URLs.

### Phase 3: Crawling

**Step 6: Trigger Crawling for Search Results**

*   **Goal:** Create and schedule background tasks for the WebCrawlerAgent to visit the URLs associated with the completed search.
*   **Command:**
    ```bash
    # Replace {SEARCH_QUERY_ID} with the ID from Step 4 (e.g., 34)
    curl -X POST http://localhost:8080/api/tasks/crawl-search-results/{SEARCH_QUERY_ID}
    ```
*   **Output:** Confirmation message including the number of crawl tasks created.
    ```json
    {
      "message": "Created and initiated 5 crawl tasks for search ID {SEARCH_QUERY_ID}.",
      "tasks_created_count": 5
    }
    ```
*   **Action:** Note the number of tasks created.

**Step 7: Identify & Poll Crawl Tasks**

*   **Goal:** Find the IDs of the newly created crawl tasks and wait for them to complete. Identify which ones succeeded.
*   **Command (Finding IDs - Fragile):**
    ```bash
    # Get recent web_crawler tasks (adjust limit if needed)
    curl -X GET "http://localhost:8080/api/tasks/?agent_type=web_crawler&limit=10" | jq
    ```
*   **Action:**
    1.  Run the command above.
    2.  Identify the most recent task IDs corresponding to the number created in Step 6 (e.g., if 5 were created, look for the 5 highest IDs: 151, 152, 153, 154, 155). This mapping is fragile.
    3.  For *each* identified crawl task ID, poll its status:
        ```bash
        # Replace {CRAWL_TASK_ID} with each ID (e.g., 151, then 152, etc.)
        curl -X GET http://localhost:8080/api/tasks/{CRAWL_TASK_ID} | jq
        ```
    4.  Repeat polling for each task until its status is `"completed"` or `"failed"`.
    5.  Note down the **Task IDs** for crawls that completed *successfully* (check `"result.status": "success"` within the completed task details).

*   **Next:** Proceed once all crawl tasks are finished. You need the list of successful `CRAWL_TASK_ID`s.

### Phase 4: Extraction

**Step 8: Trigger Extraction for Successful Crawls**

*   **Goal:** Create and schedule background tasks for the InformationExtractionAgent to process the content from each successfully crawled page.
*   **Action:** For *each* successful `CRAWL_TASK_ID` noted in Step 7, run the following command:
    ```bash
    # Replace {SUCCESSFUL_CRAWL_TASK_ID} with a succeeded ID from Step 7
    curl -X POST http://localhost:8080/api/tasks/extract-from-crawl/{SUCCESSFUL_CRAWL_TASK_ID}
    ```
*   **Output:** For each command, a confirmation message including the `extraction_task_id`.
    ```json
    {
      "message": "Created and initiated information extraction task 156 based on crawl task {SUCCESSFUL_CRAWL_TASK_ID}.",
      "extraction_task_id": 156 // Example ID
    }
    ```
*   **Action:** Collect all the `extraction_task_id`s created (e.g., `156`, `157`, `158`...).

**Step 9: Poll Extraction Tasks & Collect Results**

*   **Goal:** Wait for the LLM extraction tasks to complete and gather the extracted data.
*   **Action:** For *each* `extraction_task_id` created in Step 8, poll its status:
    ```bash
    # Replace {EXTRACTION_TASK_ID} with each ID (e.g., 156, then 157, etc.)
    curl -X GET http://localhost:8080/api/tasks/{EXTRACTION_TASK_ID} | jq
    ```
*   **Action:** Repeat polling for each task until its status is `"completed"` or `"failed"`. If completed successfully, examine the `"result.extracted_data"` field which contains the structured JSON extracted by the LLM.
*   **Action:** **Manually aggregate** the `extracted_data` dictionaries from all *successful* extraction tasks into a single list. You will need this list for the next step. (The automation script does this automatically, but here you do it manually).

    *Example Aggregated Data (Conceptual):*
    ```json
    [
      { "company_name_mentioned": "Embark IT", "summary": "...", "metrics": [...], "events": [...] },
      { "company_name_mentioned": null, "summary": "...", "metrics": [], "events": [...] },
      // ... data from other successful extractions ...
    ]
    ```

*   **Next:** Proceed once all triggered extraction tasks are finished and you have manually compiled the list of successful `extracted_data` results.

### Phase 5: Storage

**Step 10: Trigger Storage of Aggregated Data**

*   **Goal:** Send the compiled extracted data to the backend to be processed by the StorageAgent and saved to the database.
*   **Action:** Prepare the aggregated JSON data (the list compiled in Step 9) and send it in the request body.
*   **Command:**
    ```bash
    # Replace {COMPANY_ID} with the original company ID (e.g., 67)
    # Replace '[...]' with the actual JSON list of extracted_data dictionaries you compiled
    curl -X POST -H "Content-Type: application/json" \
    -d '[
      { "company_name_mentioned": "Embark IT", "summary": "...", "metrics": [{"metric_type": "revenue", "value": 1000000}], "events": [] },
      { "company_name_mentioned": null, "summary": "...", "metrics": [], "events": [{"event_type": "partnership", "details": "..."}] }
    ]' \
    http://localhost:8080/api/tasks/store-aggregated-data/{COMPANY_ID}
    ```
*   **Output:** A JSON response containing a list of `storage_task_ids`.
    ```json
    {
      "message": "Triggered 3 storage sub-tasks for Company ID {COMPANY_ID}.",
      "storage_task_ids": [ 159, 160, 161 ] // Example IDs
    }
    ```
*   **Action:** Note the `storage_task_ids`.

**Step 11: Poll Storage Tasks**

*   **Goal:** Wait for the StorageAgent to save the overview, links, metrics, and events to the database.
*   **Action:** For *each* `storage_task_id` created in Step 10, poll its status:
    ```bash
    # Replace {STORAGE_TASK_ID} with each ID (e.g., 159, then 160, etc.)
    curl -X GET http://localhost:8080/api/tasks/{STORAGE_TASK_ID} | jq
    ```
*   **Action:** Repeat polling for each task until its status is `"completed"` or `"failed"`. Check the `"result"` message for success/failure details.

### Phase 6: Verification

**Step 12: Check Updated Company Information**

*   **Goal:** Verify that the company's details (overview, links) have been updated in the database via the API.
*   **Command:**
    ```bash
    # Replace {COMPANY_ID} with the original company ID (e.g., 67)
    curl -X GET http://localhost:8080/api/companies/{COMPANY_ID} | jq
    ```
*   **Output:** The full company details JSON.
*   **Action:** Examine the `"description"` field for the updated overview and the `"source_links"` array for the stored source URLs.
*   **Action (Optional):** Connect to your database directly (using `psql` or a GUI) and check the `financial_metrics` and `company_events` tables for records associated with the `{COMPANY_ID}` to verify metric/event storage.

---

This completes the manual workflow using `curl`. Remember to check backend logs if any step fails unexpectedly.
