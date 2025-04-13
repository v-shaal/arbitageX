import nltk
import numpy as np
from typing import List, Dict, Any, Optional
import json
import re
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from llama_index.llms.gemini import Gemini
from llama_index.core import Settings
from dotenv import load_dotenv
from llama_index.core import PromptTemplate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download necessary NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
except:
    logger.warning("Failed to download NLTK data. Some NLP features may not work properly.")

class TextProcessor:
    """
    Handles text preprocessing for embedding generation and information extraction.
    """
    
    def __init__(self):
        try:
            self.stopwords = set(nltk.corpus.stopwords.words('english'))
        except:
            self.stopwords = set()
            logger.warning("Failed to load stopwords. Continuing without stopword removal.")
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text for processing"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove HTML tags
        text = re.sub(r'<.*?>', ' ', text)
        
        # Remove special characters and digits
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def remove_stopwords(self, text: str) -> str:
        """Remove stopwords from text"""
        if not text:
            return ""
        
        words = text.split()
        filtered_words = [word for word in words if word not in self.stopwords]
        return ' '.join(filtered_words)
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into sentences"""
        if not text:
            return []
        
        return nltk.sent_tokenize(text)
    
    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks of approximately chunk_size tokens"""
        if not text:
            return []
        
        sentences = self.tokenize(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed chunk size and we already have content
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap from previous chunk
                words = current_chunk.split()
                if len(words) > overlap:
                    current_chunk = ' '.join(words[-overlap:]) + ' ' + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += ' ' + sentence
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks


# --- Pydantic Models for LLM Extraction Output ---

class ExtractedMetric(BaseModel):
    """Represents a single extracted financial metric."""
    metric_type: Optional[str] = Field(None, description="Type of metric (e.g., revenue, funding_amount, employee_count, growth_rate)")
    value: Optional[float] = Field(None, description="Numeric value of the metric")
    unit: Optional[str] = Field(None, description="Unit of the value (e.g., USD, %, M, B)")
    period: Optional[str] = Field(None, description="Time period if mentioned (e.g., annual, quarterly, 2023)")
    raw_mention: Optional[str] = Field(None, description="The exact text snippet mentioning the metric")

class ExtractedEvent(BaseModel):
    """Represents a single extracted company event."""
    event_type: Optional[str] = Field(None, description="Type of event (e.g., funding_round, acquisition, partnership, launch, key_hire)")
    details: Optional[str] = Field(None, description="Key details about the event (e.g., acquired company, funding amount, partner name, person hired)")
    date: Optional[str] = Field(None, description="Date of the event if mentioned (YYYY-MM-DD or description)")
    raw_mention: Optional[str] = Field(None, description="The exact text snippet mentioning the event")

class ExtractedData(BaseModel):
    """Structured data extracted by the LLM."""
    company_name_mentioned: Optional[str] = Field(None, description="Company name explicitly mentioned in the text, if any")
    summary: Optional[str] = Field(None, description="A brief summary of the text's key points related to the company.")
    metrics: List[ExtractedMetric] = Field(default_factory=list, description="List of extracted financial or operational metrics.")
    events: List[ExtractedEvent] = Field(default_factory=list, description="List of extracted company events.")

# --- End Pydantic Models ---


class InformationExtractor:
    """
    Extracts structured information from text using Gemini LLM and JSON parsing.
    """
    
    def __init__(self):
        self.text_processor = TextProcessor()
        # LLM initialization is now handled globally via Settings in run.py
        # No longer needed here:
        # if not Settings.llm:
        #     print("Initializing Gemini LLM for InformationExtractor...")
        #     try:
        #         Settings.llm = Gemini(model_name="models/gemini-pro")
        #     except Exception as e:
        #         logger.error(f"Failed to initialize Gemini: {e}. Extraction will likely fail.")
        # else:
        #     print(f"Using pre-configured LLM: {type(Settings.llm)}")

    # Remove or comment out old regex methods
    # def extract_financial_metrics(self, text: str) -> Dict[str, Any]: ...
    # def extract_company_events(self, text: str) -> List[Dict[str, Any]]: ...
    # def _extract_date(self, text: str, position: int) -> Optional[str]: ...

    def extract_structured_data_with_llm(self, text: str, company_context: Optional[str] = None) -> ExtractedData:
        """Extracts structured data using Gemini LLM, prompting for JSON output."""
        if not Settings.llm:
            logger.error("LLM is not configured globally. Cannot perform extraction.")
            return ExtractedData()

        if not text:
            return ExtractedData()

        # Get the JSON schema for the desired output
        output_schema = ExtractedData.model_json_schema()

        # Define the prompt string
        context_str = f" focusing on information relevant to the company {company_context}" if company_context else ""
        prompt_str = f"""\nPlease analyze the following text{context_str} and extract relevant information.
Your goal is to populate a JSON object matching the following schema. 
Only output the JSON object, with no introductory text or explanations.

Schema:
```json
{json.dumps(output_schema, indent=2)}
```

Focus on financial metrics (like revenue, funding, employee count, growth rates) 
and key company events (like funding rounds, acquisitions, partnerships, product launches, key hires).
Provide a brief summary of the text's key points related to the company (if identifiable).
Identify the company name if explicitly mentioned.

Text to analyze:

{text}


JSON Output:
"""

        logger.info(f"Sending request to Gemini for structured extraction. Text length: {len(text)}")
        raw_output = "" # Initialize raw_output
        try:
            response = Settings.llm.complete(prompt_str)
            raw_output = response.text
            logger.info(f"Received raw output from LLM. Length: {len(raw_output)}")
            # print(f"Raw LLM Output:\n{raw_output}") # Uncomment for debugging

            json_str = raw_output
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_output, re.DOTALL | re.IGNORECASE)
            if json_match:
                json_str = json_match.group(1).strip()
                logger.info("Extracted JSON block from markdown.")
            else:
                json_str = raw_output.strip()
                if json_str.startswith('json'):
                    json_str = json_str[4:].strip()
                logger.info("Attempting to parse raw output as JSON (no markdown found).")

            parsed_json = json.loads(json_str)
            validated_data = ExtractedData(**parsed_json)
            logger.info("Successfully parsed and validated LLM output.")
            return validated_data # Return successful data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output from LLM: {e}\nRaw Output was: {raw_output}")
            return ExtractedData() # Return empty on parsing error
        except Exception as e:
            logger.error(f"Error processing LLM response for extraction: {e}\nRaw Output was: {raw_output}")
            return ExtractedData() # Return empty on other errors


class CompanyProfileGenerator:
    """
    Generates structured company profiles from extracted information.
    """
    
    def __init__(self):
        self.extractor = InformationExtractor()
    
    def generate_profile(self, company_name: str, texts: List[str]) -> Dict[str, Any]:
        """Generate a company profile from multiple text sources"""
        profile = {
            'name': company_name,
            'financial_metrics': {},
            'events': [],
            'description': '',
            'sources': len(texts)
        }
        
        combined_text = ' '.join(texts)
        
        # Extract financial metrics
        metrics = self.extractor.extract_financial_metrics(combined_text)
        profile['financial_metrics'] = metrics
        
        # Extract events
        events = self.extractor.extract_company_events(combined_text)
        profile['events'] = events
        
        # Generate simple description
        profile['description'] = self._generate_description(company_name, metrics, events)
        
        return profile
    
    def _generate_description(self, company_name: str, metrics: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
        """Generate a simple company description from extracted information"""
        description = f"{company_name} is a company"
        
        # Add industry if available
        # (In a real implementation, we would extract this from text)
        
        # Add financial information
        if 'revenue' in metrics:
            description += f" with annual revenue of ${metrics['revenue']}M"
        
        if 'growth_rate' in metrics:
            description += f" and a growth rate of {metrics['growth_rate']}%"
        
        if 'employee_count' in metrics:
            description += f", employing approximately {metrics['employee_count']} people"
        
        # Add recent events
        if events:
            description += ". Recent events include "
            event_descriptions = []
            
            for event in events:
                if event['event_type'] == 'acquisition':
                    date_str = f" in {event['date']}" if event.get('date') else ""
                    event_descriptions.append(f"the acquisition of {event['entity']}{date_str}")
                elif event['event_type'] == 'funding':
                    date_str = f" in {event['date']}" if event.get('date') else ""
                    event_descriptions.append(f"raising ${event['amount']}M in funding{date_str}")
            
            description += ", ".join(event_descriptions)
        
        description += "."
        return description


class SimilarityCalculator:
    """
    Calculates similarity between vectors.
    """
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        # Convert to numpy arrays for efficient calculation
        a = np.array(vec1)
        b = np.array(vec2)
        
        # Calculate cosine similarity
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def batch_cosine_similarity(self, query_vec: List[float], vectors: List[List[float]]) -> List[float]:
        """Calculate cosine similarity between query vector and multiple vectors"""
        return [self.cosine_similarity(query_vec, vec) for vec in vectors]


class CompanyScorer:
    """
    Scores companies based on investment criteria.
    """
    
    def __init__(self):
        self.similarity_calculator = SimilarityCalculator()
    
    def score_company(self, company_profile: Dict[str, Any], strategy_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Score a company based on investment criteria"""
        score_breakdown = {}
        total_score = 0.0
        total_weight = 0.0
        
        # Industry match
        if 'industry_focus' in strategy_criteria and 'industry' in company_profile:
            weight = strategy_criteria.get('weights', {}).get('industry', 1.0)
            total_weight += weight
            
            industry_match = 0.0
            if company_profile['industry'] in strategy_criteria['industry_focus']:
                industry_match = 1.0
            
            score_breakdown['industry_match'] = {
                'score': industry_match,
                'weight': weight,
                'weighted_score': industry_match * weight
            }
            total_score += industry_match * weight
        
        # Revenue criteria
        if 'revenue_range' in strategy_criteria and 'financial_metrics' in company_profile and 'revenue' in company_profile['financial_metrics']:
            weight = strategy_criteria.get('weights', {}).get('revenue', 1.0)
            total_weight += weight
            
            revenue = company_profile['financial_metrics']['revenue']
            min_revenue = strategy_criteria['revenue_range'].get('min', 0)
            max_revenue = strategy_criteria['revenue_range'].get('max', float('inf'))
            
            revenue_match = 0.0
            if min_revenue <= revenue <= max_revenue:
                revenue_match = 1.0
            elif revenue < min_revenue:
                # Partial score for being close to minimum
                revenue_match = max(0, revenue / min_revenue)
            
            score_breakdown['revenue_match'] = {
                'score': revenue_match,
                'weight': weight,
                'weighted_score': revenue_match * weight
            }
            total_score += revenue_match * weight
        
        # Growth criteria
        if 'growth_criteria' in strategy_criteria and 'financial_metrics' in company_profile and 'growth_rate' in company_profile['financial_metrics']:
            weight = strategy_criteria.get('weights', {}).get('growth', 1.0)
            total_weight += weight
            
            growth_rate = company_profile['financial_metrics']['growth_rate']
            min_growth = strategy_criteria['growth_criteria'].get('min_annual_growth', 0)
            preferred_growth = strategy_criteria['growth_criteria'].get('preferred_annual_growth', min_growth * 2)
            
            growth_match = 0.0
            if growth_rate >= preferred_growth:
                growth_match = 1.0
            elif growth_rate >= min_growth:
                # Linear scaling between min and preferred
                growth_match = (growth_rate - min_growth) / (preferred_growth - min_growth)
            
            score_breakdown['growth_match'] = {
                'score': growth_match,
                'weight': weight,
                'weighted_score': growth_match * weight
            }
            total_score += growth_match * weight
        
        # Geographic criteria
        if 'geographic_focus' in strategy_criteria and 'location' in company_profile:
            weight = strategy_criteria.get('weights', {}).get('location', 1.0)
            total_weight += weight
            
            location_match = 0.0
            for geo in strategy_criteria['geographic_focus']:
                if geo.lower() in company_profile['location'].lower():
                    location_match = 1.0
                    break
            
            score_breakdown['location_match'] = {
                'score': location_match,
                'weight': weight,
                'weighted_score': location_match * weight
            }
            total_score += location_match * weight
        
        # Normalize score
        normalized_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Generate explanation
        explanation = self._generate_explanation(company_profile, score_breakdown, normalized_score)
        
        return {
            'overall_score': normalized_score,
            'score_breakdown': score_breakdown,
            'explanation': explanation
        }
    
    def _generate_explanation(self, company_profile: Dict[str, Any], score_breakdown: Dict[str, Any], overall_score: float) -> str:
        """Generate a natural language explanation for the score"""
        company_name = company_profile.get('name', 'The company')
        
        if overall_score >= 0.8:
            quality = "excellent"
        elif overall_score >= 0.6:
            quality = "strong"
        elif overall_score >= 0.4:
            quality = "moderate"
        else:
            quality = "weak"
        
        explanation = f"{company_name} is a {quality} match with an overall score of {overall_score:.2f}. "
        
        # Add details about key factors
        factors = []
        
        if 'industry_match' in score_breakdown:
            score = score_breakdown['industry_match']['score']
            if score > 0.7:
                factors.append("industry alignment is strong")
            elif score > 0.3:
                factors.append("industry alignment is moderate")
            else:
                factors.append("industry alignment is weak")
        
        if 'revenue_match' in score_breakdown:
            score = score_breakdown['revenue_match']['score']
            if score > 0.7:
                factors.append("revenue is within target range")
            elif score > 0.3:
                factors.append("revenue is close to target range")
            else:
                factors.append("revenue is outside target range")
        
        if 'growth_match' in score_breakdown:
            score = score_breakdown['growth_match']['score']
            if score > 0.7:
                factors.append("growth rate is excellent")
            elif score > 0.3:
                factors.append("growth rate is acceptable")
            else:
                factors.append("growth rate is below target")
        
        if 'location_match' in score_breakdown:
            score = score_breakdown['location_match']['score']
            if score > 0.7:
                factors.append("location is in target region")
            else:
                factors.append("location is outside target region")
        
        if factors:
            explanation += "Key factors: " + ", ".join(factors) + "."
        
        return explanation
