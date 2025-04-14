
# ArbitrageX 

## 1. Overview

ArbitrageX is a platform designed to automate investment research and analysis by leveraging AI agents. The backend provides a robust API infrastructure for managing company data, defining investment strategies, triggering automated research workflows (web search, crawling, information extraction), and performing analysis based on defined criteria.

The core idea is to use specialized AI agents, coordinated by an orchestration layer, to gather, process, and store relevant company information, ultimately providing users with actionable insights.

## 2. Features

*   **Data Management:** API endpoints for managing Companies, Investment Strategies, and associated data (Financial Metrics, Events, Source Links - partially simulated).
*   **CSV Upload:** Bulk upload company data via CSV files.
*   **Strategy-Based Analysis:** Run analyses to score companies against predefined investment strategies based on criteria like growth rate, revenue, etc.
*   **Automated Research Workflow:** An agent-driven pipeline to research specific companies:
    *   **Search:** Uses Tavily API to find relevant web sources.
    *   **Crawl:** Uses Playwright to fetch content from web sources, handling dynamic pages.
    *   **Extract:** Uses an LLM (Gemini or OpenAI via LlamaIndex/Langchain) to extract structured information (metrics, events, summary) from crawled text.
    *   **Store:** Persists extracted information (metrics, events, links, overview) back into the database associated with the company.
*   **Agent Architecture:** Modular design with specialized agents (`SearchAgent`, `WebCrawlerAgent`, `InformationExtractionAgent`, `StorageAgent`, `AnalysisAgent`) managed by an `OrchestratorAgent`.
*   **Orchestration Layer (Langchain - WIP):** A higher-level Langchain agent (`orchestration.py`) designed to automate the multi-step research workflow using custom tools that interact with the backend API. *(Currently requires manual step progression via API calls for testing).*
*   **Configurable AI Backend:** Supports using either Google Gemini or OpenAI models as the core LLM, configurable via environment variables.
*   **Asynchronous Task Processing:** Uses FastAPI's `BackgroundTasks` for handling potentially long-running agent operations without blocking API responses.

## 3. Architecture Overview

The system employs a layered architecture:

1.  **API Layer (FastAPI):** Exposes REST endpoints (`main.py`, `agent_api.py`). Handles incoming requests, validation (Pydantic schemas in `schemas.py`), and triggers background tasks or orchestration flows.
2.  **Orchestration Layer (Langchain - `orchestration.py`):** Defines a Langchain agent (`AgentExecutor`) and custom tools (`BaseTool` subclasses) that wrap backend API calls. The agent plans and executes the sequence of tools (Search -> Crawl -> Extract -> Store) to fulfill a high-level goal like "generate company profile".
3.  **Agent Layer (`agents.py`):** Contains specialized Python classes (`SearchAgent`, `WebCrawlerAgent`, etc.) responsible for specific tasks. Managed by the `OrchestratorAgent`.
4.  **AI Core (`ai_components.py`, LlamaIndex/Langchain):** Reusable components for AI tasks. Includes `InformationExtractor` (using LLM for JSON extraction), `CompanyScorer`, etc. Global LLM configuration via LlamaIndex `Settings`.
5.  **Data Layer (`database.py`, `models.py`):** Uses SQLAlchemy to interact with the relational database (PostgreSQL/SQLite) storing operational data defined by ORM models. Also includes Pydantic schemas (`schemas.py`) for data validation.
6.  **Background Task Processing (`main.py:run_task_processor`):** Handles asynchronous execution of agent tasks triggered via FastAPI's `BackgroundTasks`, ensuring proper database session management.

## 4. Technology Stack

*   **Backend:** Python 3, FastAPI
*   **Data Validation:** Pydantic
*   **ORM:** SQLAlchemy
*   **Database:** PostgreSQL (recommended) or SQLite (current dev setup implied by errors)
*   **Web Crawling:** Playwright
*   **Web Search:** Tavily API (`tavily-python`)
*   **LLM Interaction:**
    *   LlamaIndex (`llama-index`, `llama-index-llms-gemini`) - Core interaction, global settings.
    *   Google Gemini (`google-generativeai`) or OpenAI (`openai`) - Underlying models.
*   **Orchestration:** Langchain (`langchain`, `langchain-openai`, `langchain-google-genai`)
*   **Text Processing:** NLTK
*   **API Clients (Internal):** Requests
*   **Async:** Asyncio, FastAPI `BackgroundTasks`
*   **Environment:** python-dotenv

## 5. Setup and Installation

1.  **Prerequisites:**
    *   Python 3.10+
    *   `pip` package installer
    *   Git
    *   (Recommended) PostgreSQL server running, or ensure SQLite is usable.
2.  **Clone Repository:**
    ```bash
    git clone <your-repo-url>
    cd arbitrageX # Or your project root directory
    ```
3.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # Linux/macOS
    # venv\Scripts\activate # Windows
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Install Playwright Browsers:**
    ```bash
    playwright install
    ```
6.  **Configure Environment:** See section below.
7.  **Database Setup:**
    *   Ensure your database server (e.g., PostgreSQL) is running and accessible.
    *   The application currently attempts to create tables automatically at startup via `models.Base.metadata.create_all(bind=engine)` in `main.py`. Ensure this line is uncommented if starting fresh. For production or more complex changes, setting up Alembic migrations is recommended.

## 6. Environment Configuration

Create a `.env` file in the project root directory (`/Users/Vishal/Project/arbitageX`) and add the following variables:

```dotenv
# --- Database ---
# Example for PostgreSQL:
# DATABASE_URL="postgresql+psycopg2://user:password@hostname:port/database_name"
# Example for SQLite (relative path from where run.py is executed):
DATABASE_URL="sqlite:///./arbitrageX.db"

# --- API Keys ---
GOOGLE_API_KEY="your_google_api_key_here"
TAVILY_API_KEY="your_tavily_api_key_here"
OPENAI_API_KEY="your_openai_api_key_here" # Required if using LLM_PROVIDER=OPENAI

# --- LLM Configuration ---
# Select provider: 'GEMINI' or 'OPENAI'
LLM_PROVIDER="GEMINI"
# Define model names (used if provider matches)
GEMINI_MODEL_NAME="models/gemini-1.5-pro-001"
OPENAI_MODEL_NAME="gpt-4o-mini"

# --- Backend Base URL (Used by Langchain tools) ---
# Ensure this matches where the API is running
BACKEND_API_BASE_URL="http://localhost:8080/api"

# Optional: LangSmith for tracing Langchain execution
# LANGCHAIN_TRACING_V2="true"
# LANGCHAIN_API_KEY="your_langsmith_api_key"
# LANGCHAIN_PROJECT="ArbitrageX Orchestration" # Example project name
```

*   Make sure the `DATABASE_URL` matches your database setup.
*   Provide valid API keys for the services you intend to use.
*   Set `LLM_PROVIDER` to choose between Gemini and OpenAI.

## 7. Running the Application

1.  Ensure your database is running and accessible.
2.  Ensure your `.env` file is correctly configured.
3.  Navigate to the project root directory.
4.  Start the FastAPI server:
    ```bash
    python run.py
    ```
    Alternatively, use Uvicorn directly (adjust module path if needed):
    ```bash
    uvicorn run:app --host 0.0.0.0 --port 8080 --reload
    ```
    The API should now be available at `http://localhost:8080`.

## 8. API Usage Examples (`curl`)

*(Replace placeholders like `{ID}`, `{JSON_DATA}`)*

**Find Company ID:**
```bash
curl -X GET "http://localhost:8080/api/companies/?name=Your%20Company%20Name" | jq
```

**Create Strategy:**
```bash
curl -X POST -H "Content-Type: application/json" \
-d '{ "name": "My New Strategy", "description": "...", "criteria": [{"criteria_type": "revenue", "min_value": 5000000}] }' \
http://localhost:8080/api/strategies/
```

**Run Analysis:**
```bash
# 1. Trigger Analysis (Get task_id)
curl -X POST -H "Content-Type: application/json" \
-d '{ "strategy_id": {STRATEGY_ID}, "filters": {} }' \
http://localhost:8080/api/analysis/

# 2. Poll Task Status (Replace {TASK_ID})
curl -X GET http://localhost:8080/api/tasks/{TASK_ID} | jq

# 3. Get Results (Replace {STRATEGY_ID})
curl -X GET http://localhost:8080/api/analysis/results/{STRATEGY_ID} | jq
```

**Manual Research Workflow (Example for Company ID 67):**
*(Note: The goal is for the Langchain agent to automate this)*
```bash
# 1. Trigger Master Task (Get master_task_id, e.g., 144)
curl -X POST http://localhost:8080/api/companies/67/update-overview

# 2. Poll Master Task, Get Search Task ID (e.g., 145)
curl -X GET http://localhost:8080/api/tasks/144 | jq # Repeat until running/done

# 3. Trigger Search Task Processing
curl -X POST http://localhost:8080/api/tasks/145/process

# 4. Poll Search Task, Get Search Query ID (e.g., 34)
curl -X GET http://localhost:8080/api/tasks/145 | jq # Repeat until completed

# 5. Trigger Crawling
curl -X POST http://localhost:8080/api/tasks/crawl-search-results/34

# 6. Find & Poll Crawl Tasks (e.g., find IDs 151-155, poll each)
curl -X GET "http://localhost:8080/api/tasks/?agent_type=web_crawler&limit=10" | jq
# ... Poll GET /api/tasks/{crawl_id} ... Note successful IDs (e.g., 151, 152)

# 7. Trigger Extraction for successful crawls
curl -X POST http://localhost:8080/api/tasks/extract-from-crawl/151 # Get extraction_task_id_1
curl -X POST http://localhost:8080/api/tasks/extract-from-crawl/152 # Get extraction_task_id_2

# 8. Poll Extraction Tasks & Aggregate Results
curl -X GET http://localhost:8080/api/tasks/{extraction_task_id_1} | jq # Repeat until done
curl -X GET http://localhost:8080/api/tasks/{extraction_task_id_2} | jq # Repeat until done
# Manually compile extracted_data list: '[{"summary": ...}, {"summary": ...}]'

# 9. Trigger Storage (Requires compiled data)
curl -X POST -H "Content-Type: application/json" \
-d '[{"summary": "Data from task 1", ...}, {"summary": "Data from task 2", ...}]' \
http://localhost:8080/api/tasks/store-aggregated-data/67

# 10. Poll Storage Tasks
# ... Poll GET /api/tasks/{storage_task_id} ...

# 11. Verify Final Company Data
curl -X GET http://localhost:8080/api/companies/67 | jq
```

## 9. Future Work & Improvements

*   **Full Langchain Orchestration:** Complete the implementation in `orchestration.py` (tool logic, LLM integration, API endpoint) to fully automate the research workflow.
*   **Robust Task Chaining:** Implement a reliable mechanism for chaining tasks (e.g., using the orchestrator, callbacks, or a workflow engine like LangGraph/Prefect/Dagster) instead of manual polling/triggering.
*   **Crawling Enhancements:** Improve Playwright usage (specific selectors, wait conditions, error handling, proxy rotation) for better success rates on complex websites.
*   **Storage Agent:** Add more sophisticated data merging/updating logic. Add API endpoints to retrieve stored metrics/events.
*   **Analysis Agent:** Enhance scoring logic, potentially using LLM for qualitative assessment or comparing extracted data against strategy criteria.
*   **Vector Database:** Fully integrate ChromaDB (or other) for semantic search over crawled documents or company profiles.
*   **Configuration:** Move constants (API URLs, polling params) to a central config file or load entirely from environment variables.
*   **Async Tools:** Implement `_arun` methods for Langchain tools using `httpx` for better performance.
*   **UI Integration:** Connect the orchestration triggers and results to the frontend.
*   **Testing:** Add unit and integration tests.
