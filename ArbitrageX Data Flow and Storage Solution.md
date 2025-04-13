# ArbitrageX Data Flow and Storage Solution

## Overview

This document outlines the data flow architecture and storage solution for the ArbitrageX MVP, with a particular focus on the vector database implementation. The design prioritizes efficient data processing, storage, and retrieval while using open-source and free tools suitable for a hackathon environment.

## Data Flow Architecture

### 1. Data Ingestion Flow

```
User Input → CSV/Strategy Upload → Preprocessing → Structured Data → Initial Storage
```

**Process Details**:
1. **User uploads CSV file or strategy document**
   - Frontend captures file and sends to backend API
   - Backend validates file format and structure
   - File is temporarily stored for processing

2. **Data preprocessing and normalization**
   - CSV: Column mapping, data type conversion, validation
   - Strategy: Text extraction, NLP processing, criteria extraction
   - Both: Entity normalization, deduplication, standardization

3. **Conversion to structured data model**
   - Company profiles created from CSV data
   - Investment criteria extracted from strategy documents
   - Metadata generation for search operations

4. **Initial storage in relational database**
   - Raw data stored with processing status
   - Structured data stored in normalized tables
   - Processing metadata for tracking and auditing

### 2. Web Crawling and Information Extraction Flow

```
Search Queries → Search Results → URL Prioritization → Web Crawling → Content Extraction → Information Extraction → Structured Data
```

**Process Details**:
1. **Search query generation**
   - Queries created from company names and investment criteria
   - Industry-specific terms added for context
   - Multiple query variations for comprehensive results

2. **Search execution and result collection**
   - Parallel search execution across multiple sources
   - Result deduplication and relevance scoring
   - URL extraction and metadata collection

3. **URL prioritization and crawling**
   - URLs ranked by relevance, recency, and source credibility
   - Batch processing of high-priority URLs
   - Content extraction with format-specific handlers

4. **Information extraction from crawled content**
   - Entity extraction (companies, people, metrics)
   - Relationship identification
   - Financial data extraction
   - Event and news extraction

5. **Structured data creation**
   - Mapping extracted information to data models
   - Cross-referencing with existing data
   - Confidence scoring for extracted information

### 3. Vector Processing Flow

```
Structured Data → Text Preprocessing → Chunking → Embedding Generation → Vector Storage → Indexing
```

**Process Details**:
1. **Text preparation for embedding**
   - Cleaning and normalization
   - Removal of irrelevant content
   - Formatting for optimal embedding

2. **Content chunking for long documents**
   - Semantic chunking based on content boundaries
   - Overlap between chunks for context preservation
   - Metadata attachment to chunks

3. **Embedding generation**
   - Batch processing of text chunks
   - Use of pre-trained embedding models
   - Dimension optimization if needed

4. **Vector storage and indexing**
   - Storage of vectors with metadata
   - Index creation for efficient similarity search
   - Versioning for data updates

### 4. Analysis and Scoring Flow

```
User Query → Criteria Vectorization → Vector Similarity Search → Candidate Selection → Multi-factor Scoring → Ranking → Explanation Generation → Results
```

**Process Details**:
1. **Query processing**
   - Investment criteria converted to search parameters
   - Criteria vectorization for similarity matching
   - Priority weighting based on user input

2. **Candidate company selection**
   - Vector similarity search for matching companies
   - Filtering based on hard criteria (size, location, etc.)
   - Initial candidate pool generation

3. **Multi-dimensional scoring**
   - Strategy alignment scoring
   - Financial performance scoring
   - Market position scoring
   - Growth potential scoring
   - Risk assessment scoring

4. **Result ranking and explanation**
   - Weighted scoring based on strategy priorities
   - Ranking of companies by overall score
   - Generation of natural language explanations
   - Supporting evidence collection

### 5. Result Presentation Flow

```
Analysis Results → Data Enrichment → Visualization Preparation → UI Rendering
```

**Process Details**:
1. **Result preparation**
   - Aggregation of scores and explanations
   - Collection of supporting evidence
   - Formatting for UI presentation

2. **Data enrichment**
   - Addition of contextual information
   - Relationship mapping between companies
   - Industry benchmark comparisons

3. **Visualization data preparation**
   - Data transformation for charts and graphs
   - Network relationship data for connection visualization
   - Timeline data for event visualization

4. **UI delivery**
   - Progressive loading of results
   - Caching for performance
   - Real-time updates as new data arrives

## Storage Solution Architecture

### 1. Relational Database (SQLite/PostgreSQL)

**Purpose**: Primary storage for structured data and relationships

**Data Models**:

1. **Companies**
   ```
   - company_id (PK)
   - name
   - description
   - industry
   - sub_industry
   - founding_date
   - location
   - employee_count
   - website
   - status
   - created_at
   - updated_at
   ```

2. **FinancialMetrics**
   ```
   - metric_id (PK)
   - company_id (FK)
   - metric_type (revenue, profit, growth, etc.)
   - value
   - unit
   - time_period
   - source
   - confidence_score
   - created_at
   ```

3. **People**
   ```
   - person_id (PK)
   - name
   - title
   - company_id (FK)
   - start_date
   - end_date
   - is_current
   - source
   - created_at
   ```

4. **CompanyEvents**
   ```
   - event_id (PK)
   - company_id (FK)
   - event_type (acquisition, funding, etc.)
   - event_date
   - description
   - related_companies
   - amount
   - source
   - created_at
   ```

5. **InvestmentStrategies**
   ```
   - strategy_id (PK)
   - name
   - description
   - created_at
   - updated_at
   ```

6. **StrategyCriteria**
   ```
   - criteria_id (PK)
   - strategy_id (FK)
   - criteria_type
   - importance_weight
   - min_value
   - max_value
   - description
   - created_at
   ```

7. **Documents**
   ```
   - document_id (PK)
   - title
   - url
   - source_type
   - company_id (FK, nullable)
   - content_summary
   - crawl_date
   - created_at
   ```

8. **SearchQueries**
   ```
   - query_id (PK)
   - query_text
   - target_entity
   - search_date
   - result_count
   - created_at
   ```

### 2. Vector Database (Chroma/FAISS)

**Purpose**: Storage and retrieval of vector embeddings for similarity search

**Collections**:

1. **CompanyVectors**
   ```
   - vector_id
   - company_id (reference to relational DB)
   - embedding_vector
   - embedding_type (profile, financials, etc.)
   - metadata
   - created_at
   ```

2. **DocumentVectors**
   ```
   - vector_id
   - document_id (reference to relational DB)
   - chunk_id
   - embedding_vector
   - chunk_text
   - metadata
   - created_at
   ```

3. **StrategyCriteriaVectors**
   ```
   - vector_id
   - criteria_id (reference to relational DB)
   - embedding_vector
   - metadata
   - created_at
   ```

**Implementation Approach**:
- Use Chroma for development simplicity
- Store vectors with rich metadata for filtering
- Implement approximate nearest neighbor search for performance
- Use batched operations for efficiency

### 3. Document Store (File System)

**Purpose**: Storage of raw documents and extracted content

**Organization**:
- `/data/raw_documents/` - Original files (CSV, PDF, etc.)
- `/data/processed_documents/` - Extracted and processed text
- `/data/crawled_pages/` - HTML content from web crawling
- `/data/exports/` - Generated reports and exports

**Implementation Approach**:
- Use hierarchical folder structure
- Implement file naming convention for easy retrieval
- Store metadata in accompanying JSON files
- Implement cleanup policies for temporary files

### 4. Cache Layer (Redis)

**Purpose**: Temporary storage for performance optimization

**Cache Categories**:
1. **Search Results Cache**
   - Key: Query hash
   - Value: Serialized search results
   - TTL: 24 hours

2. **Embedding Cache**
   - Key: Text hash
   - Value: Embedding vector
   - TTL: 7 days

3. **Analysis Results Cache**
   - Key: Analysis parameters hash
   - Value: Serialized analysis results
   - TTL: 1 hour

4. **UI Data Cache**
   - Key: User ID + view type
   - Value: Prepared UI data
   - TTL: 15 minutes

**Implementation Approach**:
- Use Redis for in-memory caching
- Implement key expiration policies
- Use compression for large values
- Implement cache invalidation on data updates

## Vector Database Implementation Details

### 1. Embedding Generation

**Model Selection**: Sentence-Transformers/all-MiniLM-L6-v2
- Rationale: Good balance of performance and size
- Embedding dimension: 384
- Language support: English
- License: Open-source

**Text Preprocessing**:
- Cleaning: Remove HTML, special characters
- Normalization: Lowercase, remove extra whitespace
- Tokenization: Split into sentences for granular embedding

**Chunking Strategy**:
- Chunk size: ~512 tokens
- Overlap: 50-100 tokens between chunks
- Preserve: Paragraph boundaries where possible
- Metadata: Track original position and source

**Batch Processing**:
- Batch size: 32 chunks per batch
- Parallel processing: Based on available CPU cores
- Progress tracking: Log completion percentage

### 2. Vector Storage with Chroma

**Setup**:
```python
import chromadb
from chromadb.config import Settings

client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="/data/vector_db"
))

# Create collections
company_collection = client.create_collection(name="companies")
document_collection = client.create_collection(name="documents")
strategy_collection = client.create_collection(name="strategies")
```

**Adding Vectors**:
```python
# Example: Adding company vectors
company_collection.add(
    ids=[f"company_{company_id}"],
    embeddings=[company_embedding],  # The vector
    metadatas=[{
        "company_id": company_id,
        "name": company_name,
        "industry": industry,
        "employee_count": employee_count,
        "location": location
    }]
)
```

**Querying Vectors**:
```python
# Example: Similarity search
results = company_collection.query(
    query_embeddings=[strategy_embedding],
    n_results=20,
    where={"industry": {"$in": target_industries}},
    include=["metadatas", "distances"]
)
```

### 3. Vector Search Optimization

**Filtering Strategy**:
- Pre-filtering: Use metadata filters before vector search
- Post-filtering: Apply additional filters after initial similarity search
- Hybrid approach: Combine vector similarity with keyword filtering

**Performance Optimization**:
- Index type: Hierarchical Navigable Small World (HNSW) for approximate search
- Distance metric: Cosine similarity
- Caching: Cache frequent queries and their results
- Batch queries: Group similar queries for efficiency

**Scaling Considerations**:
- Sharding: Prepare for collection sharding if data grows
- Persistence: Regular backups of vector database
- Monitoring: Track query performance and index efficiency

### 4. Vector Database Integration

**Integration with Relational Database**:
- Reference mapping: Store relational DB IDs in vector metadata
- Join strategy: Use vector search results to query relational data
- Consistency: Update vectors when relational data changes

**Integration with Analysis Engine**:
- Query construction: Convert analysis parameters to vector queries
- Result processing: Combine vector search results with other scoring factors
- Explanation generation: Use vector distances as part of explanation logic

## Data Flow Sequence Diagrams

### 1. CSV Upload and Processing

```
User → Frontend → Backend API → CSV Processor → Data Persistence → Vector Generation → Vector DB
  |       |           |             |                  |                 |                |
  | Upload CSV        |             |                  |                 |                |
  |------>|           |             |                  |                 |                |
  |       | POST /api/upload/csv    |                  |                 |                |
  |       |---------->|             |                  |                 |                |
  |       |           | Process CSV |                  |                 |                |
  |       |           |------------>|                  |                 |                |
  |       |           |             | Store structured data              |                |
  |       |           |             |----------------->|                 |                |
  |       |           |             |                  | Generate vectors|                |
  |       |           |             |                  |---------------->|                |
  |       |           |             |                  |                 | Store vectors  |
  |       |           |             |                  |                 |--------------->|
  |       |           |             |                  |                 |                |
  |       | Response with status    |                  |                 |                |
  |<------|<----------|<------------|<-----------------|<----------------|<---------------|
```

### 2. Search and Crawling Process

```
Orchestrator → Search Agent → Web Crawler → Info Extraction → Storage Agent
      |              |               |                |               |
      | Initiate search              |                |               |
      |------------->|               |                |               |
      |              | Execute search|                |               |
      |              |-------------->|                |               |
      |              | Return URLs   |                |               |
      |<-------------|               |                |               |
      | Crawl priority URLs          |                |               |
      |------------------------------>|               |               |
      |                               | Crawl content |               |
      |                               |-------------->|               |
      |                               | Extract info  |               |
      |                               |-------------->|               |
      |                               |               | Store data    |
      |                               |               |-------------->|
      |                               |               | Confirm storage
      |<------------------------------|<--------------|<--------------|
```

### 3. Analysis and Scoring Process

```
User → Frontend → Backend API → Analysis Agent → Vector DB → Relational DB → Frontend → User
  |       |           |               |              |            |            |         |
  | Request analysis  |               |              |            |            |         |
  |------>|           |               |              |            |            |         |
  |       | POST /api/analysis        |              |            |            |         |
  |       |---------->|               |              |            |            |         |
  |       |           | Process request              |            |            |         |
  |       |           |-------------->|              |            |            |         |
  |       |           |               | Vector search|            |            |         |
  |       |           |               |------------->|            |            |         |
  |       |           |               | Return matches            |            |         |
  |       |           |               |<-------------|            |            |         |
  |       |           |               | Get detailed data         |            |         |
  |       |           |               |--------------------------->|            |         |
  |       |           |               | Return data  |            |            |         |
  |       |           |               |<---------------------------|            |         |
  |       |           |               | Score and rank            |            |         |
  |       |           |               |------------->|            |            |         |
  |       |           | Return results|              |            |            |         |
  |       |<----------|<--------------|              |            |            |         |
  |       | Display results           |              |            |            |         |
  |<------|           |               |              |            |            |         |
```

## Data Security and Privacy Considerations

### 1. Data Protection

- Implement access controls for sensitive data
- Encrypt data at rest for persistent storage
- Sanitize and validate all user inputs
- Implement proper error handling without information leakage

### 2. Ethical Web Crawling

- Respect robots.txt directives
- Implement appropriate crawl delays
- Use identifiable user agents
- Store only processed data, not raw content when possible
- Implement data retention policies

### 3. API Security

- Use API keys for external service access
- Rotate credentials regularly
- Store credentials securely (environment variables)
- Implement rate limiting for external API calls

## Scalability and Performance Considerations

### 1. Horizontal Scaling

- Design stateless components for easy replication
- Use message queues for task distribution
- Implement connection pooling for database access
- Design for independent scaling of components

### 2. Vertical Scaling

- Optimize memory usage for vector operations
- Implement efficient algorithms for data processing
- Use batch operations for database interactions
- Optimize query patterns for performance

### 3. Caching Strategy

- Implement multi-level caching
- Cache frequently accessed data
- Implement proper cache invalidation
- Use compression for large cached items

## Implementation Roadmap

### Phase 1: Core Data Infrastructure

1. Set up relational database schema
2. Implement CSV processing pipeline
3. Set up vector database with basic collections
4. Implement embedding generation pipeline

### Phase 2: Data Acquisition Components

1. Implement search integration
2. Develop web crawling engine
3. Build information extraction system
4. Create data storage and indexing pipeline

### Phase 3: Analysis and Presentation

1. Implement vector similarity search
2. Develop scoring and ranking algorithms
3. Create explanation generation system
4. Build data visualization components

## Conclusion

The ArbitrageX data flow and storage solution is designed to efficiently process, store, and analyze company data for private equity investment opportunities. By leveraging open-source vector database technology and efficient data processing pipelines, the system can provide valuable insights while meeting the constraints of a hackathon MVP environment.
