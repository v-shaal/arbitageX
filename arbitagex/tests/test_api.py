#!/usr/bin/env python3
import os
import sys
import unittest
import requests
import json
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the main app from run.py AFTER setting env vars if needed
# Load environment variables (optional here, but good practice)
from dotenv import load_dotenv
load_dotenv()
if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = "dummy_test_key_google"

from run import app # Import the main app from run.py
from backend.database import Base, engine

# Create test client using the main app
client = TestClient(app)

class TestArbitrageXAPI(unittest.TestCase):
    """Test suite for ArbitrageX API endpoints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and create tables"""
        # Create tables (consider using a separate test DB)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        """Drop database tables after tests"""
        Base.metadata.drop_all(bind=engine)
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)
    
    def test_create_company(self):
        """Test company creation endpoint"""
        company_data = {
            "name": "Test Company",
            "industry": "Technology",
            "sub_industry": "Software",
            "location": "San Francisco, CA",
            "employee_count": 100,
            "website": "https://testcompany.com"
        }
        response = client.post("/api/companies/", json=company_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], company_data["name"])
        self.assertEqual(data["industry"], company_data["industry"])
        self.assertIn("id", data)
    
    def test_get_companies(self):
        """Test get companies endpoint"""
        response = client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
    
    def test_create_strategy(self):
        """Test strategy creation endpoint"""
        strategy_data = {
            "name": "Test Strategy",
            "description": "A test investment strategy",
            "criteria": [
                {
                    "criteria_type": "revenue",
                    "importance_weight": 1.5,
                    "min_value": 10000000,
                    "max_value": 100000000,
                    "description": "Revenue between $10M and $100M"
                },
                {
                    "criteria_type": "growth_rate",
                    "importance_weight": 2.0,
                    "min_value": 15,
                    "description": "Growth rate above 15%"
                }
            ]
        }
        response = client.post("/api/strategies/", json=strategy_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], strategy_data["name"])
        self.assertEqual(data["description"], strategy_data["description"])
        self.assertIn("id", data)
        self.assertIn("criteria", data)
        self.assertEqual(len(data["criteria"]), 2)
    
    def test_get_strategies(self):
        """Test get strategies endpoint"""
        response = client.get("/api/strategies/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
    
    def test_create_search(self):
        """Test search creation endpoint"""
        search_data = {
            "query": "innovative software companies",
            "target_entity": "company"
        }
        response = client.post("/api/search/", json=search_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("search_id", data)
        self.assertIn("task_id", data)
    
    def test_create_analysis(self):
        """Test analysis creation endpoint"""
        # First create a strategy
        strategy_data = {
            "name": "Analysis Test Strategy",
            "description": "A test strategy for analysis"
        }
        strategy_response = client.post("/api/strategies/", json=strategy_data)
        strategy_id = strategy_response.json()["id"]
        
        # Now create analysis
        analysis_data = {
            "strategy_id": strategy_id,
            "filters": {
                "industry": "Technology"
            }
        }
        response = client.post("/api/analysis/", json=analysis_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("task_id", data)
    
    # Mock LlamaIndexOrchestrator methods for agent endpoint tests
    @patch('backend.llamaindex_agents.LlamaIndexOrchestrator.extract_information', new_callable=AsyncMock)
    @patch('backend.agent_api.profile_generator') # Patch the instance variable itself
    @patch('llama_index.embeddings.gemini.GeminiEmbedding.get_text_embedding')
    def test_agent_endpoints(self, mock_get_embedding, mock_profile_generator_instance, mock_extract_info):
        """Test agent-specific endpoints with mocked backend logic"""
        
        # Configure mocks
        mock_extract_info.return_value = {
            "status": "success",
            "extracted_data": { "company_name": "Mock Co", "financial_metrics": {"revenue": 10}, "events": [] }
        }
        # Configure the generate_profile method on the mocked instance
        mock_profile_generator_instance.generate_profile.return_value = {
            "name": "TechCorp", "financial_metrics": {"revenue": 45}, "description": "Mock profile"
        }
        mock_get_embedding.return_value = [0.1] * 768 # Mock embedding vector
        
        # -- Test /api/agents/extract-information (called by agent_api.py) --
        text = "TechCorp Inc reported annual revenue of $45M with a growth rate of 22% in 2023."
        response = client.post("/api/agents/extract-information", json={"text": text}) 
        self.assertEqual(response.status_code, 200, f"Error: {response.text}") # Include error message on failure
        data = response.json()
        self.assertIn("financial_metrics", data)
        self.assertIn("events", data)
        self.assertIn("embedding_sample", data)
        self.assertEqual(len(data["embedding_sample"]), 5) # Check sample length
        mock_get_embedding.assert_called() # Verify embedding was generated
        # Note: mock_extract_info is NOT called by this specific API endpoint

        # -- Test /api/agents/generate-profile (called by agent_api.py) --
        profile_data = {
            "company_name": "TechCorp",
            "texts": [
                "TechCorp Inc reported annual revenue of $45M with a growth rate of 22% in 2023.",
                "TechCorp has 120 employees and is based in Boston, MA."
            ]
        }
        response = client.post("/api/agents/generate-profile", json=profile_data) 
        self.assertEqual(response.status_code, 200, f"Error: {response.text}")
        data = response.json()
        self.assertEqual(data["name"], "TechCorp")
        self.assertIn("financial_metrics", data)
        self.assertIn("description", data)
        # Assert call on the mocked instance's method
        mock_profile_generator_instance.generate_profile.assert_called_once_with("TechCorp", profile_data["texts"])

    # Add tests for other agent endpoints (/process-tasks, /score-company, /calculate-similarity) 
    # using similar mocking strategies if needed.

if __name__ == "__main__":
    unittest.main()
