#!/usr/bin/env python3
import os
import sys
import unittest
import asyncio
import json # Import json
import chromadb # Import chromadb
from unittest.mock import MagicMock, patch, AsyncMock
from dotenv import load_dotenv
import requests # Import requests

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Set a dummy key if real one isn't present (tests might still need this)
if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = "dummy_test_key_google"
if not os.environ.get("TAVILY_API_KEY"):
    os.environ["TAVILY_API_KEY"] = "dummy_test_key_tavily"

# Import backend modules AFTER potentially setting env vars
from backend.llamaindex_agents import LlamaIndexOrchestrator # Only need orchestrator for tool testing
from backend.database import Base, engine # Import DB components if needed for setup/teardown
from backend.models import Document as SQLDocument # Alias SQL Document

# --- Test Config ---
TEST_CHROMA_PATH = "./chroma_db_test_data"
TEST_COLLECTION_NAME = "test_arbitragex_documents"
# --- End Test Config ---

# Remove class decorator
# @patch('chromadb.PersistentClient') 
class TestLlamaIndexAgents(unittest.TestCase):
    """Test suite for LlamaIndex-based agent system"""

    @classmethod
    def setUpClass(cls):
        """Set up test ChromaDB and ensure clean state."""
        if os.path.exists(TEST_CHROMA_PATH):
            import shutil
            shutil.rmtree(TEST_CHROMA_PATH)
        os.makedirs(TEST_CHROMA_PATH, exist_ok=True)
        # We might also need to setup/teardown SQL tables if tests interact
        # Base.metadata.create_all(bind=engine) 

    @classmethod
    def tearDownClass(cls):
        """Clean up test ChromaDB."""
        if os.path.exists(TEST_CHROMA_PATH):
            import shutil
            shutil.rmtree(TEST_CHROMA_PATH)
        # Base.metadata.drop_all(bind=engine)

    def setUp(self): # Removed mock_chroma_client from signature
        """Set up test orchestrator with mocks for external dependencies (SQL DB)."""
        self.db_mock = MagicMock() # Mock the SQLAlchemy session
        
        # Patch the chromadb client within this setup method's scope
        with patch('chromadb.PersistentClient') as mock_chroma_client:
            # Configure the mock client instance
            mock_instance = MagicMock()
            mock_chroma_client.return_value = mock_instance
            # Configure the mock collection
            mock_collection = MagicMock()
            mock_instance.get_or_create_collection.return_value = mock_collection

            # Now instantiate the orchestrator - it will use the patched Chroma client/collection
            self.orchestrator = LlamaIndexOrchestrator(self.db_mock)
            
            # Verify the mock PersistentClient was called during orchestrator init INSIDE the patch context
            mock_chroma_client.assert_called_once_with(path=os.path.join(os.getcwd(), "chroma_db_data"))

    def test_task_to_query_conversion(self):
        """Test conversion of tasks to natural language queries"""
        # This test remains the same as it doesn't hit external services
        query = self.orchestrator._task_to_query("web_search", {"query": "innovative tech companies"})
        self.assertIn("Search for companies", query)
        query = self.orchestrator._task_to_query("crawl_url", {"url": "https://example.com"})
        self.assertIn("Extract content from this URL", query)
        query = self.orchestrator._task_to_query("extract_information", {})
        self.assertIn("Extract key information", query)

    # Test Web Search with Mocking
    @patch('tavily.TavilyClient.search', new_callable=AsyncMock)
    async def async_test_search_web(self, mock_tavily_search):
        """Test search web functionality with Tavily mocked"""
        # Configure mock return value for Tavily
        mock_tavily_search.return_value = {
            "results": [
                {"title": "Mock Title 1", "url": "http://mock1.com", "content": "Mock snippet 1"},
                {"title": "Mock Title 2", "url": "http://mock2.com", "content": "Mock snippet 2"}
            ]
        }
        
        result = await self.orchestrator.search_web("innovative tech companies")
        mock_tavily_search.assert_called_once_with(query="innovative tech companies", search_depth="basic", max_results=7)
        self.assertEqual(result["status"], "success")
        self.assertIsInstance(result["results"], list)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["title"], "Mock Title 1")

    # Test Crawling with Mocking
    @patch('requests.get')
    async def async_test_crawl_url(self, mock_requests_get):
        """Test crawl URL functionality with requests mocked"""
        # Configure mock response for requests.get
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b"<html><head><title>Mock Page</title></head><body><p>Mock content</p></body></html>"
        mock_requests_get.return_value = mock_response
        
        test_url = "https://mock-crawl.com"
        result = await self.orchestrator.crawl_url(test_url)
        
        mock_requests_get.assert_called_once()
        # Check if URL matches (it's the first arg)
        self.assertEqual(mock_requests_get.call_args[0][0], test_url)
        # Check if headers are present
        self.assertIn('headers', mock_requests_get.call_args[1])
        self.assertIn('User-Agent', mock_requests_get.call_args[1]['headers'])
        
        self.assertEqual(result["status"], "success")
        self.assertIn("Mock content", result["content"])
        self.assertIsNotNone(result["document_id"])

    # Test Extraction with Mocking
    @patch('llama_index.llms.gemini.Gemini.acomplete', new_callable=AsyncMock)
    async def async_test_extract_information(self, mock_gemini_acomplete):
        """Test information extraction functionality with Gemini LLM mocked"""
        # Configure mock response for Gemini
        mock_llm_response = MagicMock()
        mock_llm_response.text = json.dumps({
            "company_name": "Mock Extracted Co",
            "financial_metrics": {"revenue": 50, "growth_rate": 10},
            "events": []
        })
        mock_gemini_acomplete.return_value = mock_llm_response
        
        test_text = "This is mock text about Mock Extracted Co with $50M revenue."
        result = await self.orchestrator.extract_information(test_text)
        
        mock_gemini_acomplete.assert_called_once()
        # Check that the input text was part of the prompt sent to the LLM
        self.assertIn(test_text, mock_gemini_acomplete.call_args[0][0]) 
        
        self.assertEqual(result["status"], "success")
        self.assertIn("extracted_data", result)
        self.assertEqual(result["extracted_data"]["company_name"], "Mock Extracted Co")
        self.assertEqual(result["extracted_data"]["financial_metrics"]["revenue"], 50)

    # Test Vector Storage with Mocking
    async def async_test_store_document_vectors(self):
        """Test document vector storage, mocking index insertion."""
        
        # Mock the index insertion directly
        with patch.object(self.orchestrator.index, 'insert_nodes') as mock_insert_nodes:
            text = "Sample document content for vector storage testing."
            result = await self.orchestrator.store_document_vectors(1, text)
            
            mock_insert_nodes.assert_called_once() # Check if index insertion was called
            
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["document_id"], 1)
            self.assertGreater(result["chunk_count"], 0)

    # Test Vector Query with Mocking
    @patch('llama_index.core.base.base_query_engine.BaseQueryEngine.query')
    async def async_test_query_vector_store(self, mock_query_engine_query):
        """Test vector store querying, mocking the query engine directly"""
        
        # Mock query engine response (synchronous mock)
        mock_response_node = MagicMock()
        mock_response_node.node.metadata = {"document_id": "1"}
        mock_response_node.node.get_content.return_value = "Mock response chunk."
        mock_response_node.score = 0.9
        
        mock_query_response = MagicMock()
        mock_query_response.source_nodes = [mock_response_node]
        mock_query_response.response = "Mock summary response."
        # Configure the mock function itself to return the response object
        mock_query_engine_query.return_value = mock_query_response

        # Note: We don't need to store vectors first because we mock the query response
        query = "What is ArbitrageX?"
        result = await self.orchestrator.query_vector_store(query)
        
        mock_query_engine_query.assert_called_once_with(query)

        self.assertEqual(result["status"], "success")
        self.assertIsInstance(result["results"], list)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["document_id"], "1")
        self.assertEqual(result["summary_response"], "Mock summary response.")

    # Combined runner for async tests
    def test_async_methods(self): # Removed mock_chroma_client from signature
        """Run all async test methods"""
        # Orchestrator already setup with mocks in setUp
        asyncio.run(self.async_test_search_web())
        asyncio.run(self.async_test_crawl_url())
        asyncio.run(self.async_test_extract_information())
        asyncio.run(self.async_test_store_document_vectors())
        asyncio.run(self.async_test_query_vector_store())
    
    # Remove tests for old specialized agents and main agent if they are obsolete
    # def test_specialized_agents(self): ...
    # def test_main_orchestrator_agent(self): ...

if __name__ == "__main__":
    unittest.main()
