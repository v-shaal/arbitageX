# ArbitrageX MVP - Implementation Guide

This guide outlines the technical implementation details for the ArbitrageX MVP built for the hackathon.

## Goal

To demonstrate an AI-driven deal sourcing engine capable of identifying, analyzing, scoring, and explaining potential investment targets based on a user-defined strategy and optional company list, using web data and agentic AI.

## Core Technologies

*   **AI Agents Framework:** LlamaIndex
*   **Web Crawling:** `crawl4ai`
*   **Vector Database:** ChromaDB
*   **Language Model (LLM):** Google Gemini (via API)
*   **Embedding Model:** HuggingFace (`bge-small-en-v1.5` or similar) via `SentenceTransformers` / `llama-index-embeddings-huggingface`
*   **Backend API:** Python (FastAPI)
*   **Data Handling:** Pandas
*   **(Optional) Frontend:** Streamlit

## Project Structure

```
arbitageX/
├── .env                  # API Keys (e.g., GOOGLE_API_KEY) - DO NOT COMMIT
├── .gitignore
├── implementation-guide.md # This file
├── requirements.txt      # Python dependencies
├── notebooks/            # Jupyter notebooks for experimentation
├── data/                 # Input data (CSVs, strategies) - add to .gitignore if sensitive
├── chroma_db_data/       # Persistent ChromaDB storage - add to .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point and API endpoints
│   ├── agents.py         # LlamaIndex Agent definitions and tool setup
│   ├── vector_db.py      # ChromaDB client setup and interactions
│   ├── crawling.py       # Wrapper/utility functions for crawl4ai
│   ├── search.py         # Wrapper/utility functions for web search tool
│   ├── schemas.py        # Pydantic models for API requests/responses
│   └── config.py         # Configuration loading (e.g., API keys from .env)
└── (Optional) app.py     # Streamlit frontend application
```

## Setup

1.  **Clone Repository:** `git clone <repo_url>`
2.  **Create Virtual Environment:** `python -m venv venv && source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
3.  **Install Dependencies:** `pip install -r requirements.txt`
4.  **Configure Environment:** Create a `.env` file in the root directory and add necessary API keys:
    ```
    GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
    # Add other keys if needed (e.g., Brave Search API key)
    ```
5.  **Run Backend:** `uvicorn src.main:app --reload` (for development)
6.  **(Optional) Run Frontend:** `streamlit run app.py`

## Components

### 1. Backend API (`src/main.py`)

*   Uses FastAPI.
*   **Endpoints:**
    *   `POST /upload/csv`: Accepts CSV file upload. Parses company names/websites using Pandas. Stores relevant data.
    *   `POST /upload/strategy`: Accepts strategy text/JSON. Parses and stores the investment thesis.
    *   `POST /process`: Triggers the main sourcing workflow orchestrating the agents. Takes strategy and optional CSV data as input. Returns job ID or status.
    *   `GET /results`: Retrieves the ranked list of sourced companies from ChromaDB. Supports filtering/pagination.
    *   `GET /explain/{company_id}`: Retrieves details and the AI-generated explanation for a specific company from ChromaDB via the Explanation Agent.

### 2. Data Input (`src/schemas.py`, `src/main.py`)

*   **CSV:** Expected format: `Company Name`, `Website` (other columns optional). Parsed using Pandas.
*   **Strategy:** Plain text or simple JSON defining target sectors, keywords, financial metrics (EBITDA range, revenue), geography, etc.
*   Pydantic models in `schemas.py` define the structure for API request bodies and responses.

### 3. Agent Architecture (`src/agents.py`, LlamaIndex)

*   Leverages LlamaIndex `AgentRunner` or similar orchestration.
*   **LLM:** Configured with `llama-index-llms-gemini`.
*   **Embedding Model:** Configured with `llama-index-embeddings-huggingface`.
*   **Agents & Tools:**
    *   **Research Agent:**
        *   *Input:* Strategy, (optional) initial company list.
        *   *Tool:* `WebSearchTool` (defined in `src/search.py`) - Uses a free search API/wrapper (e.g., Brave Search, DuckDuckGo) to find companies and relevant article URLs matching the strategy.
        *   *Output:* List of potential company names and relevant URLs.
    *   **Crawling Agent:**
        *   *Input:* List of URLs.
        *   *Tool:* `CrawlingTool` (defined in `src/crawling.py`) - Wraps `crawl4ai` to fetch and clean text content from URLs. Includes basic error handling.
        *   *Output:* Dictionary `{url: content}`.
    *   **Analysis Agent:**
        *   *Input:* Crawled text content for a company.
        *   *Tool:* `GeminiLLMTool` (via LlamaIndex) with specific prompts.
        *   *Task:* Extracts key information: company overview, recent signals (funding, M&A, exec changes, partnerships, conference mentions), alignment with strategy keywords.
        *   *Output:* Structured data (e.g., JSON/dict) with extracted info.
    *   **Scoring Agent:**
        *   *Input:* Structured analysis data, investment strategy.
        *   *Tool:* `GeminiLLMTool` (or custom Python logic).
        *   *Task:* Scores the company based on predefined criteria (sector fit, signal relevance, size indicators if available) defined in the strategy.
        *   *Output:* Numerical score and brief justification.
    *   **Storage Agent:**
        *   *Input:* Processed company data (analysis, score, metadata).
        *   *Tool:* `ChromaDBTool` (using `ChromaVectorStore` from LlamaIndex or direct client from `src/vector_db.py`), `HuggingFaceEmbeddingTool`.
        *   *Task:* Generates text embedding (e.g., from analysis summary), stores the data and vector in ChromaDB with appropriate metadata (company name, URL, score, source, timestamp). Uses `upsert` to handle updates.
        *   *Output:* Confirmation of storage.
    *   **Explanation Agent:**
        *   *Input:* Company ID/Name.
        *   *Tool:* `ChromaDBQueryEngine` (using `VectorStoreIndex` or similar from LlamaIndex), `GeminiLLMTool`.
        *   *Task:* Retrieves company data from ChromaDB. Uses the LLM to synthesize the information and generate a natural language explanation of *why* the company was identified and scored highly, referencing specific signals and strategy alignment.
        *   *Output:* Text explanation.

### 4. Web Crawling (`src/crawling.py`, `crawl4ai`)

*   Uses the `crawl4ai` library.
*   A wrapper function/tool handles calling `crawl4ai`, extracting primary content, and basic error handling (timeouts, request errors).

### 5. Vector Database (`src/vector_db.py`, ChromaDB)

*   Uses `chromadb` client.
*   Initializes a persistent client pointing to `./chroma_db_data/`.
*   Creates/gets a collection named `companies`.
*   Stores vectors generated from company analysis summaries.
*   Metadata associated with each vector includes: `company_name`, `url`, `score`, `extracted_signals` (list or JSON string), `analysis_summary`, `source_strategy_id`, `timestamp`.
*   Enables similarity search to find related companies or query based on natural language.

### 6. Core Workflow (`/process` endpoint in `src/main.py`)

1.  Receive strategy and optional CSV via API.
2.  **Research:** Trigger Research Agent to find initial URLs based on strategy/CSV.
3.  **Crawl:** For each relevant URL, trigger Crawling Agent to get text content.
4.  **Analyze:** For each crawled page, trigger Analysis Agent to extract structured info and signals.
5.  **Score:** Trigger Scoring Agent to evaluate fit against the strategy.
6.  **Store:** Trigger Storage Agent to embed summary and store all data in ChromaDB.
7.  Return status/job ID.

### 7. Results & Explanation (`/results`, `/explain` endpoints)

*   `/results`: Queries ChromaDB, potentially filtering by score or strategy ID, returns ranked list.
*   `/explain`: Retrieves specific company data from ChromaDB, passes it to the Explanation Agent (LLM) to generate the reasoning.

## Key Features Implementation

*   **Target Identification:** Handled by Research Agent (Web Search) + Analysis Agent (extracting relevance).
*   **Signal Detection:** Primarily done by the Analysis Agent, specifically prompted to look for funding news, executive changes, partnerships, etc., in crawled text.
*   **Scoring & Prioritization:** Handled by the Scoring Agent based on strategy criteria. Results endpoint returns ranked list.
*   **Preemptive Sourcing:** Achieved implicitly by continuously monitoring *web* sources (news, press releases found via search) rather than relying solely on databases like PitchBook/Crunchbase (which often lag). The freshness of web crawling is key.

## Future Improvements (Post-Hackathon)

*   Integrate specific data sources beyond generic web search (SEC filings, specific news APIs).
*   Implement relationship intelligence (requires CRM/LinkedIn data - likely out of scope for hackathon).
*   More sophisticated scoring models.
*   Persistent background job queue (Celery, RQ) for long-running sourcing tasks.
*   User authentication and multi-tenancy.
*   Enhanced UI/Dashboard.
*   Feedback loop for users to rate sourced deals, improving the scoring model. 