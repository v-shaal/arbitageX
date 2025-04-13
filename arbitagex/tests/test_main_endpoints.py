#!/usr/bin/env python3
import os
import sys
import unittest
import requests
import json
import io
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

from run import app  # Import the main app from run.py
from backend.database import Base, engine

# Create test client using the main app
client = TestClient(app)

class TestMainEndpoints(unittest.TestCase):
    """Test suite for ArbitrageX API endpoints from main.py"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and create tables"""
        # Create tables
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        """Drop database tables after tests"""
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        """Set up before each test if needed"""
        # Will remain empty for now, can add setup logic if needed
        pass
    
    def tearDown(self):
        """Clean up after each test if needed"""
        # Will remain empty for now, can add teardown logic if needed
        pass
    
    # ---- Base API Tests ----
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/api/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("version", data)
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)
    
    # ---- Company Endpoint Tests ----
    
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
        return data["id"]  # Return ID for use in other tests
    
    def test_get_companies(self):
        """Test get companies endpoint"""
        # Create a company first to ensure there's at least one
        self.test_create_company()
        
        response = client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Test pagination
        response = client.get("/api/companies/?skip=0&limit=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data), 2)
    
    def test_get_company_by_id(self):
        """Test get company by ID endpoint"""
        # Create a company and get its ID
        company_id = self.test_create_company()
        
        # Get the company by ID
        response = client.get(f"/api/companies/{company_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], company_id)
        
        # Test non-existent company
        response = client.get("/api/companies/99999")
        self.assertEqual(response.status_code, 404)
    
    # ---- Investment Strategy Endpoint Tests ----
    
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
        return data["id"]  # Return ID for use in other tests
    
    def test_get_strategies(self):
        """Test get strategies endpoint"""
        # Create a strategy first to ensure there's at least one
        self.test_create_strategy()
        
        response = client.get("/api/strategies/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Test pagination
        response = client.get("/api/strategies/?skip=0&limit=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data), 2)
    
    def test_get_strategy_by_id(self):
        """Test get strategy by ID endpoint"""
        # Create a strategy and get its ID
        strategy_id = self.test_create_strategy()
        
        # Get the strategy by ID
        response = client.get(f"/api/strategies/{strategy_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], strategy_id)
        
        # Test non-existent strategy
        response = client.get("/api/strategies/99999")
        self.assertEqual(response.status_code, 404)
    
    # ---- CSV Upload Endpoint Tests ----
    
    def test_upload_csv(self):
        """Test CSV upload endpoint"""
        # Create a mock CSV file in memory
        csv_content = """name,industry,sub_industry,location,employee_count,revenue,growth_rate
Test CSV Company,Technology,SaaS,New York,150,50000000,25.5
Second Test Co,Finance,Banking,Chicago,300,100000000,12.3
"""
        file = io.BytesIO(csv_content.encode())
        file.name = "test_companies.csv"
        
        response = client.post(
            "/api/upload/csv/",
            files={"file": ("test_companies.csv", file, "text/csv")},
            data={"mapping_template": json.dumps({"name": "name", "industry": "industry"})}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["upload_id"], "test_companies.csv")
        self.assertEqual(data["row_count"], 2)
        self.assertEqual(data["companies_created"], 2)
        self.assertIn("preview_data", data)
        self.assertIn("columns", data)
    
    # ---- Strategy Document Upload Endpoint Tests ----
    
    def test_upload_strategy_document(self):
        """Test strategy document upload endpoint"""
        # Create a mock PDF file in memory
        pdf_content = b"%PDF-1.4 mock content"
        file = io.BytesIO(pdf_content)
        file.name = "test_strategy.pdf"
        
        response = client.post(
            "/api/upload/strategy/",
            files={"file": ("test_strategy.pdf", file, "application/pdf")},
            data={"strategy_name": "Test Uploaded Strategy"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["strategy_name"], "Test Uploaded Strategy")
        self.assertIn("strategy_id", data)
        self.assertIn("document_id", data)
    
    # ---- Search Endpoint Tests ----
    
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
        return data["search_id"]  # Return ID for use in other tests
    
    def test_get_search_results(self):
        """Test get search results endpoint"""
        # Create a search first
        search_id = self.test_create_search()
        
        # Get results (will be empty initially)
        response = client.get(f"/api/search/{search_id}/results")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        
        # Manually insert a mock result for testing
        # This would normally be done by background task
        with patch("backend.models.SearchResult") as MockSearchResult:
            mock_result = MagicMock()
            mock_result.query_id = search_id
            mock_result.title = "Test Result"
            mock_result.url = "https://example.com"
            mock_result.snippet = "A test search result"
            mock_result.rank = 1
            MockSearchResult.return_value = mock_result
    
    # ---- Analysis Endpoint Tests ----
    
    def test_create_analysis(self):
        """Test analysis creation endpoint"""
        # First create a strategy
        strategy_id = self.test_create_strategy()
        
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
        
        # Test with non-existent strategy
        analysis_data["strategy_id"] = 99999
        response = client.post("/api/analysis/", json=analysis_data)
        self.assertEqual(response.status_code, 404)
    
    def test_get_analysis_results(self):
        """Test get analysis results endpoint"""
        # First create a strategy
        strategy_id = self.test_create_strategy()
        
        # Get results (will be empty initially)
        response = client.get(f"/api/analysis/results/{strategy_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
    
    # ---- Agent Task Endpoint Tests ----
    
    def test_get_task_status(self):
        """Test get task status endpoint"""
        # First create a task via search
        search_data = {
            "query": "task status test",
            "target_entity": "company"
        }
        search_response = client.post("/api/search/", json=search_data)
        task_id = search_response.json()["task_id"]
        
        # Get task status
        response = client.get(f"/api/tasks/{task_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], task_id)
        self.assertEqual(data["status"], "pending")
        
        # Test non-existent task
        response = client.get("/api/tasks/99999")
        self.assertEqual(response.status_code, 404)
    
    def test_get_tasks(self):
        """Test get tasks endpoint"""
        # First create a task via search
        search_data = {
            "query": "list tasks test",
            "target_entity": "company"
        }
        client.post("/api/search/", json=search_data)
        
        # Get all tasks
        response = client.get("/api/tasks/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Test filtering by type
        response = client.get("/api/tasks/?agent_type=search")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for task in data:
            self.assertEqual(task["agent_type"], "search")
        
        # Test filtering by status
        response = client.get("/api/tasks/?status=pending")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for task in data:
            self.assertEqual(task["status"], "pending")
        
        # Test pagination
        response = client.get("/api/tasks/?skip=0&limit=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data), 2)

if __name__ == "__main__":
    unittest.main() 