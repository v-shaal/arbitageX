# ArbitrageX Backend Architecture Document

## 1. Overview

ArbitrageX is a platform designed to assist users in investment research and analysis. The backend provides APIs for managing company data, investment strategies, performing automated research (web search, crawling, information extraction), running analyses based on strategies, and orchestrating these complex workflows using AI agents. The goal is to automate the gathering, processing, and analysis of company information to identify potential investment opportunities.

## 2. High-Level Architecture

The system follows a layered architecture:

1.  **Frontend:** (Not detailed here, but interacts via REST API) A web-based user interface allowing users to manage strategies, view companies, trigger analyses, and initiate research.
2.  **Backend API (FastAPI):** Exposes RESTful endpoints for all frontend interactions and potentially for external system integration. Handles request validation, basic business logic, and delegates complex tasks to the agent layer.
3.  **Orchestration Layer (Langchain):** (Newly added) Manages multi-step workflows like full company profile generation. Uses a Langchain agent and custom tools which interact with the Backend API/Agent Layer.
4.  **Agent Layer:** Contains specialized agents responsible for specific tasks (search, crawl, extract, store, analyze). These are triggered by API endpoints or the Orchestration Layer.
5.  **AI Core (LlamaIndex, Gemini, AI Components):** Provides the core AI capabilities – primarily LLM interaction for reasoning and information extraction, potentially vector embeddings and search.
6.  **Data Storage:** Persists application data using relational databases (via SQLAlchemy) and potentially vector databases (via LlamaIndex integrations like ChromaDB - *initial assumption, needs confirmation*).
7.  **External Services:** Integrates with third-party APIs for specific functions (e.g., Tavily for search).

## 3. Technology Stack

*   **Backend Framework:** Python, FastAPI (Chosen for its async capabilities, performance, automatic data validation via Pydantic, and ease of use).
*   **Data Validation:** Pydantic (Used extensively by FastAPI for request/response models and within schemas).
*   **Database ORM:** SQLAlchemy (Standard Python ORM for interacting with relational databases).
*   **Relational Database:** PostgreSQL (implied by `psycopg2-binary`) or SQLite (implied by `sqlite3` errors) - Used for storing structured operational data (companies, strategies, tasks, results, links, metrics, events).
*   **Web Crawling:** Playwright (Chosen over basic `requests` for its ability to render JavaScript and handle dynamic web pages, essential for bypassing anti-scraping measures on sites like Crunchbase, D&B, etc.).
*   **AI - LLM Interaction:**
    *   **LlamaIndex:** Manages interaction with the core LLM (Google Gemini). Configured globally via `llama_index.core.Settings` to provide a consistent LLM instance. Used for the LLM-powered information extraction (`InformationExtractor`).
    *   **Google Gemini:** The primary Large Language Model used (specifically `gemini-1.5-pro-002` configured). Accessed via `llama-index-llms-gemini`.
    *   **Langchain Google GenAI:** The `langchain-google-genai` wrapper (`ChatGoogleGenerativeAI`) is used to make the globally configured Gemini LLM compatible with the Langchain agent framework.
*   **AI - Orchestration:**
    *   **Langchain:** Used for the high-level orchestration agent (`orchestration.py`). Leverages Langchain's `AgentExecutor` and agent creation functions (`create_react_agent`) to manage multi-step workflows involving custom tools. The agent uses the LLM (Gemini via wrapper) as its reasoning engine to decide which tool to use next.
*   **AI - Search:**
    *   **Tavily Search API:** Used via the `tavily-python` client within the `SearchAgent` to perform web searches optimized for AI agent consumption.
*   **Task Processing:** FastAPI `BackgroundTasks` (Provides a simple mechanism for running tasks asynchronously after an API response is sent, suitable for triggering agent processing).
*   **Text Processing:** NLTK (Used for basic text operations like tokenization, potentially stopword removal, within `ai_components.py` and `agents.py`).
*   **HTTP Requests:** `requests` (Used within Langchain tools to interact with the backend API).

## 4. Detailed Component Breakdown

### 4.1. Backend API (FastAPI - `main.py`, `run.py`)

*   **Role:** Entry point for all external interactions. Defines REST endpoints using FastAPI routers.
*   **Functionality:**
    *   CRUD operations for `Company`, `InvestmentStrategy`, `CompanySourceLink`.
    *   Endpoints to trigger agent tasks (`/api/search/`, `/api/analysis/`, `/api/tasks/.../process`, `/api/tasks/crawl-search-results/...`, `/api/tasks/extract-from-crawl/...`, `/api/tasks/store-aggregated-data/...`).
    *   Endpoints to trigger high-level orchestration (`POST /api/companies/{id}/update-overview`).
    *   Endpoints to retrieve task status (`GET /api/tasks/{id}`) and results (`GET /api/search/{id}/results`, `GET /api/analysis/results/{id}`).
    *   Uses Pydantic schemas (`schemas.py`) for request/response validation.
    *   Injects database sessions (`Depends(get_db)`) and `BackgroundTasks`.
    *   Utilizes the `run_task_processor` utility function to schedule agent tasks asynchronously via `BackgroundTasks`, ensuring proper DB session handling for background jobs.
*   **AI Interaction:** Primarily delegates tasks to the Agent Layer or Orchestration Layer.

### 4.2. Database & Data Models (`database.py`, `models.py`, `schemas.py`)

*   **Role:** Defines and manages data persistence.
*   **Components:**
    *   `database.py`: Configures the SQLAlchemy engine, `SessionLocal` factory, and the `get_db` dependency injector. Reads database URL potentially from environment variables.
    *   `models.py`: Defines SQLAlchemy ORM models (`Company`, `FinancialMetric`, `Person`, `CompanyEvent`, `InvestmentStrategy`, `StrategyCriteria`, `Document`, `SearchQuery`, `SearchResult`, `CompanySourceLink`, `AgentTask`, etc.). Defines table structures and relationships.
    *   `schemas.py`: Defines Pydantic models used for API request/response validation and data transfer objects. Often mirrors ORM models but provides API-specific views.
*   **AI Interaction:** Stores the *inputs* and *outputs* of AI processes (e.g., `AgentTask` records, `SearchResult` records, extracted `FinancialMetric` / `CompanyEvent` records). Does not perform AI operations itself.

### 4.3. Agent Layer (`agents.py`)

*   **Role:** Encapsulates specific, potentially long-running business logic units. Designed for modularity.
*   **Components:**
    *   **`OrchestratorAgent`:** Initially responsible for processing individual tasks scheduled via `run_task_processor`. Handles routing tasks to the correct specialized agent based on `agent_type`. Was extended to handle the `generate_full_profile` *orchestration task*, initiating the first step (Search). *NOTE: The new Langchain-based orchestrator (`orchestration.py`) is intended to eventually take over complex multi-step workflows.*
    *   **`SearchAgent`:**
        *   Handles `"search" / "web_search"` tasks.
        *   Uses the **Tavily API Client (`tavily-python`)** to perform web searches.
        *   Stores results (`SearchResult`) in the relational database.
    *   **`WebCrawlerAgent`:**
        *   Handles `"web_crawler" / "crawl_url"` tasks.
        *   Uses **Playwright** to launch a browser, navigate to URLs, and extract text content, aiming to handle dynamic sites and basic anti-scraping.
        *   Updates the `is_processed` flag on the corresponding `SearchResult`.
    *   **`InformationExtractionAgent`:**
        *   Handles `"information_extraction" / "extract_from_content"` tasks.
        *   Relies on the `InformationExtractor` component from `ai_components.py`.
        *   Calls the LLM (**Gemini via LlamaIndex `Settings.llm`**) using a detailed prompt asking for JSON output matching the `ExtractedData` Pydantic schema.
        *   Parses and validates the LLM's JSON response.
    *   **`StorageAgent`:**
        *   Handles various `"storage"` tasks (`"store_extracted_data"`, `"store_company_overview"`, `"store_company_links"`).
        *   Takes processed data (e.g., extracted metrics/events, generated overview, found links) and persists it into the appropriate relational database tables (`FinancialMetric`, `CompanyEvent`, `Company`, `CompanySourceLink`) linked to the correct `Company` record.
    *   **`AnalysisAgent`:**
        *   Handles `"analysis" / "company_analysis"` tasks.
        *   Retrieves companies and strategy criteria from the database.
        *   Applies filtering logic.
        *   Scores companies based on criteria (current implementation is basic, could be enhanced with LLM).
        *   Stores `AnalysisResult` records.
*   **AI Interaction:** `SearchAgent` uses Tavily. `WebCrawlerAgent` uses Playwright (indirectly AI-relevant for accessing data). `InformationExtractionAgent` uses the core LLM (Gemini). `AnalysisAgent` could potentially use an LLM for more nuanced scoring.

### 4.4. AI Core (`ai_components.py`, LlamaIndex/Gemini Config)

*   **Role:** Provides reusable AI-powered functionalities used by the agents.
*   **Components:**
    *   `InformationExtractor`: Contains the core logic for extracting structured data from text using the **Gemini LLM via LlamaIndex `Settings.llm.complete()`** and JSON prompting. Defines Pydantic models (`ExtractedData`, `ExtractedMetric`, `ExtractedEvent`) for the desired output structure.
    *   `CompanyScorer`: Scores companies against criteria (currently rule-based).
    *   `TextProcessor`: Basic text cleaning utilities (using `re`, potentially `nltk`).
    *   `SimilarityCalculator`: Placeholder for potential vector similarity calculations.
    *   `CompanyProfileGenerator`: Placeholder for generating text summaries.
    *   **LlamaIndex Settings (`run.py`)**: Globally configures the **Gemini LLM (`llama_index.llms.gemini.Gemini`)** instance used across the application, ensuring consistent access. Potentially configures embedding models (`GeminiEmbedding`) if vector search becomes a feature.

### 4.5. Langchain Orchestration (`orchestration.py`)

*   **Role:** Provides a higher-level, automated workflow manager using a Langchain agent framework. Designed to replace manual, multi-step API calls for complex processes like profile generation.
*   **Components:**
    *   **Custom Tools (`BaseTool` subclasses):** `SearchCompanyTool`, `CrawlURLsTool`, `ExtractInformationTool`, `StoreCompanyDataTool`. These tools act as wrappers around the existing backend API endpoints, essentially allowing the Langchain agent to interact with the established agent task system. They handle triggering tasks and polling for results.
    *   **Agent Executor (`AgentExecutor`):** The runtime environment for the Langchain agent. It iteratively invokes the agent, executes the chosen tools, and feeds results back to the agent. Uses `create_react_agent` (ReAct framework).
    *   **LLM Integration (`ChatGoogleGenerativeAI`):** Uses the Langchain wrapper for the globally configured Gemini model to serve as the reasoning engine for the agent.
    *   **Prompting (`PromptTemplate`):** Defines the instructions and context given to the LLM agent, explaining its goal and how to use the available tools.
*   **AI Interaction:** Deeply integrated. Uses the **Gemini LLM** for planning and deciding which tool to use next. Tools themselves trigger other AI agents (Search, Extract).

### 4.6. Task Processing (`main.py: run_task_processor`, FastAPI `BackgroundTasks`)

*   **Role:** Enables asynchronous execution of agent tasks.
*   **Mechanism:**
    1.  API endpoints create `AgentTask` records in the DB with `status="pending"`.
    2.  FastAPI `BackgroundTasks` is used to schedule the `run_task_processor` function *after* the API response is sent.
    3.  `run_task_processor` creates a *new, independent database session* (`SessionLocal()`) specifically for the background task.
    4.  It instantiates the `OrchestratorAgent` with this new session.
    5.  It calls `OrchestratorAgent.process_task(task_id)`.
    6.  The `OrchestratorAgent` routes the task to the appropriate specialized agent, which performs the work using the dedicated session.
    7.  Ensures the session is closed properly.
*   **Design Choice:** Using `BackgroundTasks` is simpler than setting up Celery/Redis but less robust for heavy loads or complex task dependencies. Creating independent sessions in the background function is crucial for database interaction safety in async contexts.

## 5. Data Flow / Key Workflows

### 5.1. Profile Generation (Langchain Orchestration)

1.  **Trigger:** `POST /api/companies/{id}/generate-profile` (Not fully implemented yet).
2.  **Initiation:** API calls `orchestration.run_profile_generation(id, name)`.
3.  **Agent Execution:** `run_profile_generation` sets up the Langchain `AgentExecutor` with tools and LLM. Invokes the agent with the goal prompt.
4.  **Tool: Search:** Agent calls `SearchCompanyTool` -> Tool calls `POST /api/search/` -> `SearchAgent` task runs (uses **Tavily**) -> Tool polls task -> Tool calls `GET /api/search/{sid}/results` -> Tool returns URLs and `search_query_id`.
5.  **Tool: Crawl:** Agent calls `CrawlURLsTool` with `search_query_id` -> Tool calls `POST /api/tasks/crawl-search-results/{sid}` -> Multiple `WebCrawlerAgent` tasks run (use **Playwright**) -> Tool polls tasks -> Tool returns `{crawl_task_id: content}` for successful crawls.
6.  **Tool: Extract:** Agent calls `ExtractInformationTool` with `{crawl_task_id: content}` -> Tool calls `POST /api/tasks/extract-from-crawl/{cid}` for each -> Multiple `InformationExtractionAgent` tasks run (use **Gemini LLM via LlamaIndex**) -> Tool polls tasks -> Tool returns aggregated list of `extracted_data` dictionaries.
7.  **Tool: Store:** Agent calls `StoreCompanyDataTool` with `company_id` and aggregated data -> Tool calls `POST /api/tasks/store-aggregated-data/{cid}` -> Multiple `StorageAgent` tasks run (update DB) -> Tool polls tasks -> Tool returns confirmation.
8.  **Completion:** Agent generates final summary response.

### 5.2. Strategy Analysis (Manual Trigger via API)

1.  **Trigger:** `POST /api/analysis/` with `strategy_id`.
2.  **Task Creation:** Endpoint creates `AnalysisAgent` task record (`generate_company_analysis`).
3.  **Scheduling:** `run_task_processor` schedules `OrchestratorAgent.process_task`.
4.  **Execution:** `OrchestratorAgent` routes to `AnalysisAgent`.
5.  **Analysis:** `AnalysisAgent` fetches strategy/companies, applies scoring logic, stores `AnalysisResult` records.
6.  **Polling:** Client polls `GET /api/tasks/{task_id}`.
7.  **Results:** Client fetches `GET /api/analysis/results/{strategy_id}`.

## 6. Design Choices & Rationale

*   **Micro-agents (`agents.py`):** Breaking down functionality into specialized agents (Search, Crawl, Extract, Store, Analyze) promotes modularity, testability, and allows for independent scaling or replacement of components.
*   **Task-Based Asynchronicity (`AgentTask` model, `BackgroundTasks`):** Using a database table (`agent_tasks`) to track work items allows API endpoints to return quickly while processing happens in the background. FastAPI's `BackgroundTasks` provides a simple entry point for this, suitable for moderate workloads. Ensures database session safety via `run_task_processor`.
*   **Playwright for Crawling:** Explicitly chosen over simpler libraries like `requests`/`BeautifulSoup` due to the requirement to scrape modern, JavaScript-heavy websites (like Crunchbase, D&B) which often employ anti-scraping techniques.
*   **Tavily for Search:** Selected as a search API optimized for AI agent workflows, potentially providing more concise and relevant results compared to standard web search APIs.
*   **LLM for Extraction (Gemini/LlamaIndex):** Moved from fragile regex to a powerful LLM for extracting structured information from unstructured web content. LlamaIndex provides convenient abstractions for interacting with Gemini. Prompting for JSON output is used as a robust method for structured data generation.
*   **Langchain for Orchestration:** Introduced to automate the complex, multi-step workflow of profile generation. Langchain agents provide a framework for LLM-driven planning and tool execution, allowing the system to dynamically chain the individual agent tasks (Search -> Crawl -> Extract -> Store) without requiring manual intervention between steps. Custom Tools bridge the Langchain agent with the existing backend task infrastructure.
*   **Relational DB for Core Data:** Standard practice for storing structured operational data like users, companies, strategies, tasks, and structured results.
*   **API-Driven Tools (Langchain):** The Langchain tools primarily interact with the system via its own backend API endpoints. This promotes decoupling – the Langchain orchestrator doesn't need intimate knowledge of the agent's internal implementation, only its API contract.

## 7. Future Considerations / Improvements

*   **Robust Orchestration:** Replace the placeholder/manual triggering logic with a fully implemented Langchain agent flow or a dedicated workflow engine (like Prefect, Dagster, or LangGraph) for better state management, error handling, and retries in multi-step processes.
*   **Centralized Status Tracking:** Implement a mechanism (e.g., Redis, DB table) to track the status of high-level orchestration runs (`run_id`) initiated by the Langchain agent.
*   **Crawling Enhancements:** Implement more sophisticated Playwright techniques (rotating user agents, handling CAPTCHAs/logins if necessary, specific element selectors instead of generic body text) to improve success rates on difficult sites. Consider using residential proxies.
*   **Vector Database Integration:** Fully implement LlamaIndex features for embedding crawled content or company profiles and storing/querying them in a vector store (like the configured ChromaDB) for semantic search or RAG capabilities.
*   **StorageAgent Robustness:** Add more sophisticated logic for merging/updating data in the `StorageAgent` (e.g., handling duplicate metrics/events, updating confidence scores).
*   **UI Integration:** Connect the new orchestration endpoints (`/generate-profile`) and status tracking to the frontend UI. Display stored financials, news/events, and sources on company detail pages.
*   **Configuration Management:** Move constants like API URLs and polling parameters to a dedicated configuration file or environment variables.
*   **Async Tool Implementation:** Implement true asynchronous `_arun` methods for Langchain tools using `httpx` and `asyncio` for improved performance when running multiple tools concurrently.
*   **Error Handling & Retries:** Implement more granular error handling and retry logic within agents and tools.