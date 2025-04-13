#!/usr/bin/env python3
import os
import sys
import unittest
import time
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import backend modules
from backend import models
from backend.agents import (
    OrchestratorAgent,
    DataIngestionAgent,
    SearchAgent,
    WebCrawlerAgent,
    InformationExtractionAgent,
    AnalysisAgent,
    StorageAgent
)
from backend.database import SessionLocal, engine, Base

class TestAgentSystem(unittest.TestCase):
    """Test suite for ArbitrageX agent system"""
    
    @classmethod
    def setUpClass(cls):
        """Create database tables before tests"""
        # Ensure tables are created (idempotent)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        """Drop database tables after tests"""
        # Drop all tables
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        """Set up test database session"""
        self.db = SessionLocal()
    
    def tearDown(self):
        """Close database session and clear data (optional, can be slow)"""
        # Rollback any uncommitted changes
        self.db.rollback()
        # Optional: Clear specific tables if needed between tests, 
        # but tearDownClass handles full cleanup.
        self.db.close()
    
    def test_orchestrator_agent(self):
        """Test orchestrator agent functionality"""
        orchestrator = OrchestratorAgent(self.db)
        
        # Test task creation
        task_id = asyncio.run(orchestrator.create_task(
            agent_type="search",
            task_type="web_search",
            params={"query": "test query", "target_entity": "test company"}
        ))
        self.assertIsNotNone(task_id)
        
        # Get task from database
        task = self.db.query(models.AgentTask).filter(models.AgentTask.id == task_id).first()
        self.assertIsNotNone(task)
        self.assertEqual(task.agent_type, "search")
        self.assertEqual(task.task_type, "web_search")
        self.assertEqual(task.status, "pending")
    
    def test_data_ingestion_agent(self):
        """Test data ingestion agent functionality"""
        agent = DataIngestionAgent(self.db)
        
        # Test process_csv method
        result = asyncio.run(agent.process_csv({
            "file_path": "test.csv",
            "mapping": {"name": "company_name", "industry": "sector"}
        }))
        self.assertEqual(result["status"], "success")
    
    def test_search_agent(self):
        """Test search agent functionality"""
        agent = SearchAgent(self.db)
        
        # Create a dummy search query first
        dummy_query = models.SearchQuery(query_text="test query", target_entity="test company")
        self.db.add(dummy_query)
        self.db.commit()
        self.db.refresh(dummy_query)

        # Test web_search method
        result = asyncio.run(agent.web_search({
            "query": "test query",
            "target_entity": "test company"
        }))
        self.assertEqual(result["status"], "success")
        self.assertIn("results", result)
        self.assertGreater(len(result["results"]), 0)
    
    def test_web_crawler_agent(self):
        """Test web crawler agent functionality"""
        agent = WebCrawlerAgent(self.db)
        
        # Test crawl_url method
        result = asyncio.run(agent.crawl_url({
            "url": "https://example.com/test",
            "query_id": 1
        }))
        self.assertEqual(result["status"], "success")
        self.assertIn("document_id", result)
    
    def test_information_extraction_agent(self):
        """Test information extraction agent functionality"""
        agent = InformationExtractionAgent(self.db)
        
        # Create a dummy document first (without specifying id)
        dummy_doc = models.Document(title="Test Doc For Extraction", source_type="test")
        self.db.add(dummy_doc)
        self.db.commit()
        self.db.refresh(dummy_doc) # Refresh to get the assigned ID
        
        # Test extract_information method using the assigned ID
        result = asyncio.run(agent.extract_information({
            "document_id": dummy_doc.id, 
            "content": "<html><body><p>Test company with $45M revenue and 22% growth.</p></body></html>"
        }))
        self.assertEqual(result["status"], "success")
        self.assertIn("extracted_data", result)
    
    def test_analysis_agent(self):
        """Test analysis agent functionality"""
        agent = AnalysisAgent(self.db)
        
        # Test analyze_companies method
        result = asyncio.run(agent.analyze_companies({
            "strategy_id": 1,
            "filters": {"industry": "Technology"}
        }))
        self.assertEqual(result["status"], "success")
        self.assertIn("results", result)
    
    def test_storage_agent(self):
        """Test storage agent functionality"""
        agent = StorageAgent(self.db)
        
        # Test store_document_vectors method
        result = asyncio.run(agent.store_document_vectors({
            "document_id": 1,
            "text_content": "This is a test document for vector storage."
        }))
        self.assertEqual(result["status"], "success")
        self.assertIn("chunk_count", result)

if __name__ == "__main__":
    unittest.main()
