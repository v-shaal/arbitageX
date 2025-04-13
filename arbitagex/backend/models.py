from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Company(Base):
    """Model for storing company information."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    industry = Column(String(100), index=True)
    sub_industry = Column(String(100), nullable=True)
    founding_date = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    employee_count = Column(Integer, nullable=True)
    website = Column(String(255), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    financial_metrics = relationship("FinancialMetric", back_populates="company")
    events = relationship("CompanyEvent", back_populates="company")
    people = relationship("Person", back_populates="company")
    analysis_results = relationship("AnalysisResult", back_populates="company")

class FinancialMetric(Base):
    """Model for storing company financial metrics."""
    __tablename__ = "financial_metrics"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    metric_type = Column(String(50), index=True)  # revenue, profit, growth, etc.
    value = Column(Float)
    unit = Column(String(20))  # USD, %, etc.
    time_period = Column(String(50))  # Q1 2023, FY 2022, etc.
    source = Column(String(255), nullable=True)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="financial_metrics")

class Person(Base):
    """Model for storing people associated with companies."""
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    title = Column(String(255), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_current = Column(Boolean, default=True)
    source = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="people")

class CompanyEvent(Base):
    """Model for storing company events like acquisitions, funding, etc."""
    __tablename__ = "company_events"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    event_type = Column(String(50), index=True)  # acquisition, funding, etc.
    event_date = Column(DateTime)
    description = Column(Text)
    related_companies = Column(JSON, nullable=True)
    amount = Column(Float, nullable=True)
    source = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="events")

class InvestmentStrategy(Base):
    """Model for storing investment strategies."""
    __tablename__ = "investment_strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    criteria = relationship("StrategyCriteria", back_populates="strategy")
    analysis_results = relationship("AnalysisResult", back_populates="strategy")

class StrategyCriteria(Base):
    """Model for storing criteria for investment strategies."""
    __tablename__ = "strategy_criteria"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("investment_strategies.id"))
    criteria_type = Column(String(50), index=True)
    importance_weight = Column(Float, default=1.0)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    strategy = relationship("InvestmentStrategy", back_populates="criteria")

class Document(Base):
    """Model for storing documents related to companies."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    url = Column(String(512), nullable=True)
    source_type = Column(String(50))  # web, pdf, csv, etc.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    content_summary = Column(Text, nullable=True)
    crawl_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vector_embeddings = relationship("DocumentVector", back_populates="document")

class SearchQuery(Base):
    """Model for storing search queries."""
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(String(512))
    target_entity = Column(String(255), nullable=True)
    search_date = Column(DateTime, default=datetime.utcnow)
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    search_results = relationship("SearchResult", back_populates="query")

class SearchResult(Base):
    """Model for storing search results."""
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("search_queries.id"))
    title = Column(String(512))
    url = Column(String(512))
    snippet = Column(Text, nullable=True)
    rank = Column(Integer)
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    query = relationship("SearchQuery", back_populates="search_results")

class CompanyVector(Base):
    """Model for storing vector embeddings for companies."""
    __tablename__ = "company_vectors"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    embedding_type = Column(String(50))  # profile, financials, etc.
    embedding_vector = Column(JSON)  # Store as JSON array
    embedding_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy reserved name
    created_at = Column(DateTime, default=datetime.utcnow)

class DocumentVector(Base):
    """Model for storing vector embeddings for document chunks."""
    __tablename__ = "document_vectors"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    chunk_id = Column(String(50))
    chunk_text = Column(Text)
    embedding_vector = Column(JSON)  # Store as JSON array
    embedding_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy reserved name
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="vector_embeddings")

class StrategyCriteriaVector(Base):
    """Model for storing vector embeddings for strategy criteria."""
    __tablename__ = "strategy_criteria_vectors"

    id = Column(Integer, primary_key=True, index=True)
    criteria_id = Column(Integer, ForeignKey("strategy_criteria.id"))
    embedding_vector = Column(JSON)  # Store as JSON array
    embedding_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy reserved name
    created_at = Column(DateTime, default=datetime.utcnow)

class AnalysisResult(Base):
    """Model for storing analysis results."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    strategy_id = Column(Integer, ForeignKey("investment_strategies.id"))
    overall_score = Column(Float)
    explanation = Column(Text)
    score_breakdown = Column(JSON)  # Detailed scoring by criteria
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="analysis_results")
    strategy = relationship("InvestmentStrategy", back_populates="analysis_results")

class AgentTask(Base):
    """Model for storing agent tasks."""
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String(50))  # search, crawler, extraction, etc.
    task_type = Column(String(50))
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
