from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Company schemas
class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    location: Optional[str] = None
    employee_count: Optional[int] = None
    website: Optional[str] = None
    status: Optional[str] = "active"

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Financial Metric schemas
class FinancialMetricBase(BaseModel):
    metric_type: str
    value: float
    unit: str
    time_period: str
    source: Optional[str] = None
    confidence_score: Optional[float] = 1.0

class FinancialMetricCreate(FinancialMetricBase):
    company_id: int

class FinancialMetric(FinancialMetricBase):
    id: int
    company_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Person schemas
class PersonBase(BaseModel):
    name: str
    title: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_current: Optional[bool] = True
    source: Optional[str] = None

class PersonCreate(PersonBase):
    company_id: int

class Person(PersonBase):
    id: int
    company_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Company Event schemas
class CompanyEventBase(BaseModel):
    event_type: str
    event_date: datetime
    description: str
    related_companies: Optional[Dict[str, Any]] = None
    amount: Optional[float] = None
    source: Optional[str] = None

class CompanyEventCreate(CompanyEventBase):
    company_id: int

class CompanyEvent(CompanyEventBase):
    id: int
    company_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Strategy Criteria schemas
class StrategyCriteriaBase(BaseModel):
    criteria_type: str
    importance_weight: Optional[float] = 1.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: Optional[str] = None

class StrategyCriteriaCreate(StrategyCriteriaBase):
    pass

class StrategyCriteria(StrategyCriteriaBase):
    id: int
    strategy_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Investment Strategy schemas
class InvestmentStrategyBase(BaseModel):
    name: str
    description: Optional[str] = None

class InvestmentStrategyCreate(InvestmentStrategyBase):
    criteria: Optional[List[StrategyCriteriaCreate]] = None

class InvestmentStrategy(InvestmentStrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    criteria: List[StrategyCriteria] = []

    class Config:
        orm_mode = True

# Document schemas
class DocumentBase(BaseModel):
    title: str
    url: Optional[str] = None
    source_type: str
    content_summary: Optional[str] = None

class DocumentCreate(DocumentBase):
    company_id: Optional[int] = None

class Document(DocumentBase):
    id: int
    company_id: Optional[int] = None
    crawl_date: datetime
    created_at: datetime

    class Config:
        orm_mode = True

# Search schemas
class SearchCreate(BaseModel):
    query: str
    target_entity: Optional[str] = None

class SearchResponse(BaseModel):
    search_id: int
    task_id: int
    status: str
    message: str

class SearchResultBase(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    rank: int
    is_processed: bool = False

class SearchResult(SearchResultBase):
    id: int
    query_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Analysis schemas
class AnalysisCreate(BaseModel):
    strategy_id: int
    filters: Optional[Dict[str, Any]] = None

class AnalysisResponse(BaseModel):
    task_id: int
    status: str
    message: str

class AnalysisResultBase(BaseModel):
    overall_score: float
    explanation: str
    score_breakdown: Dict[str, Any]

class AnalysisResult(AnalysisResultBase):
    id: int
    company_id: int
    strategy_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Agent Task schemas
class AgentTaskBase(BaseModel):
    agent_type: str
    task_type: str
    status: str = "pending"
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AgentTask(AgentTaskBase):
    id: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Upload response schemas
class CSVUploadResponse(BaseModel):
    upload_id: str
    status: str
    row_count: int
    columns: List[str]
    preview_data: List[Dict[str, Any]]
    companies_created: int

class StrategyUploadResponse(BaseModel):
    strategy_id: int
    strategy_name: str
    status: str
    document_id: int
    message: str
