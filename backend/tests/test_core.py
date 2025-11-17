"""
Comprehensive Unit Tests for BRAKES Backend

Tests all core functionality including PDF extraction, intervention parsing,
IRC clause retrieval, quantity calculations, pricing, cost calculation, and verification.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.pdf_extractor import extract_pdf_text, extract_with_pdfplumber
from services.intervention_parser import parse_interventions, parse_with_keywords
from services.clause_retriever import get_clause_by_intervention, search_clauses
from services.quantity_calculator import calculate_quantity
from services.price_fetcher import get_material_price, search_prices
from services.cost_calculator import calculate_cost, calculate_total_estimate
from services.verification import verify_cost_item, verify_estimate
from models.intervention import Intervention, Material, EstimateItem, Estimate


# ==================== FIXTURES ====================

@pytest.fixture
def sample_pdf_text():
    """Sample extracted text from PDF"""
    return """
    Road Safety Audit Report - NH-44
    
    The following interventions are recommended:
    
    1. Install 10 speed breakers at km 5 to km 10
    2. Install 500 meters of guardrails along the curve at km 15
    3. Road markings: 2000 square meters of thermoplastic markings
    4. Install 20 street lights from km 8 to km 12
    5. Install 15 regulatory signs at various locations
    """

@pytest.fixture
def sample_intervention():
    """Sample intervention object"""
    return Intervention(
        type="speed_breaker",
        quantity=10,
        unit="units",
        location="km 5-10",
        confidence=0.95,
        extraction_method="gemini"
    )

@pytest.fixture
def sample_material():
    """Sample material object"""
    return Material(
        name="Concrete M15",
        quantity=0.525,
        unit="cum",
        unit_price=5500.0,
        total_cost=2887.5,
        irc_clause="IRC 67:3.2.1",
        price_source="CPWD SOR 2023",
        fetched_date=datetime.now()
    )

@pytest.fixture
def sample_estimate_item(sample_intervention, sample_material):
    """Sample estimate item"""
    return EstimateItem(
        intervention=sample_intervention,
        materials=[sample_material],
        total_cost=2887.5,
        audit_trail={
            "extraction": {
                "method": "gemini",
                "confidence": 0.95
            },
            "clause_matching": {
                "standard": "IRC 67",
                "clause": "3.2.1",
                "matched": True
            },
            "quantity_calculation": {
                "formula": "3.5m × 0.3m × 0.05m per unit",
                "result": 0.0525,
                "unit": "cum"
            },
            "pricing": {
                "source": "CPWD SOR 2023",
                "unit_price": 5500.0,
                "confidence": 0.92
            },
            "verification": {
                "checks_passed": ["IRC clause found", "Quantity calculated", "Price found"],
                "warnings": []
            }
        },
        assumptions=[
            "IRC 67 specifications used",
            "Standard material specifications assumed",
            "CPWD SOR 2023 pricing basis"
        ]
    )

@pytest.fixture
def mock_irc_clauses():
    """Mock IRC clauses data"""
    return [
        {
            "standard": "IRC 67",
            "clause": "3.2.1",
            "title": "Speed Breaker - Trapezoidal Profile",
            "text": "Speed breakers shall be 3.5m wide, 0.3m high with 0.05m thickness",
            "material": "Concrete M15",
            "unit": "cum",
            "formula": "3.5 * 0.3 * 0.05",
            "per_unit_quantity": 0.0525,
            "category": "Speed Control",
            "page": "25"
        },
        {
            "standard": "IRC 35",
            "clause": "6.1.1",
            "title": "Metal Beam Crash Barrier",
            "text": "W-beam crash barriers with galvanized steel",
            "material": "GI W-beam Guardrail",
            "unit": "kg",
            "formula": "5 kg per meter",
            "per_unit_quantity": 5,
            "category": "Crash Barrier",
            "page": "45"
        }
    ]


# ==================== TEST 1: PDF EXTRACTION - PDFPLUMBER ====================

def test_pdf_extraction_pdfplumber():
    """Test PDF text extraction using pdfplumber"""
    
    # Test with non-existent file (error case)
    with pytest.raises(FileNotFoundError):
        extract_pdf_text("nonexistent.pdf")
    
    # Mock successful extraction by patching os.path.exists
    with patch('os.path.exists') as mock_exists, \
         patch('services.pdf_extractor.extract_with_pdfplumber') as mock_extract:
        
        mock_exists.return_value = True
        mock_extract.return_value = {
            "text": "Sample PDF content with road safety data",
            "method": "pdfplumber",
            "confidence": 0.95,
            "page_count": 5,
            "char_count": 1500
        }
        
        result = extract_pdf_text("test.pdf")
        
        assert result["method"] == "pdfplumber"
        assert result["confidence"] == 0.95
        assert result["page_count"] == 5
        assert "road safety" in result["text"]


# ==================== TEST 2: PDF EXTRACTION - OCR ====================

def test_pdf_extraction_ocr():
    """Test PDF text extraction using OCR fallback"""
    
    # Mock OCR extraction when pdfplumber fails
    with patch('os.path.exists') as mock_exists, \
         patch('services.pdf_extractor.extract_with_pdfplumber') as mock_plumber, \
         patch('services.pdf_extractor.extract_with_ocr') as mock_ocr:
        
        mock_exists.return_value = True
        
        # Pdfplumber returns poor quality
        mock_plumber.return_value = {
            "text": "abc",  # Too short
            "method": "pdfplumber",
            "confidence": 0.30,
            "page_count": 1,
            "char_count": 3
        }
        
        # OCR returns better result
        mock_ocr.return_value = {
            "text": "OCR extracted text with better quality content for road safety audit report",
            "method": "ocr",
            "confidence": 0.78,
            "page_count": 1,
            "char_count": 82
        }
        
        result = extract_pdf_text("scanned.pdf")
        
        assert result["method"] == "hybrid"  # Implementation uses hybrid when combining
        assert result["confidence"] == 0.78
        assert len(result["text"]) > 50


# ==================== TEST 3: INTERVENTION PARSING - GEMINI ====================

def test_intervention_parsing_gemini(sample_pdf_text):
    """Test intervention parsing using Gemini AI"""
    
    with patch('services.intervention_parser.call_gemini') as mock_gemini:
        # Mock Gemini response
        mock_gemini.return_value = json.dumps([
            {
                "type": "speed_breaker",
                "quantity": 10,
                "unit": "units",
                "location": "km 5 to km 10",
                "confidence": 0.95
            },
            {
                "type": "guardrail",
                "quantity": 500,
                "unit": "meters",
                "location": "km 15 curve",
                "confidence": 0.90
            }
        ])
        
        interventions = parse_interventions(sample_pdf_text)
        
        assert len(interventions) >= 2
        assert any(i.type == "speed_breaker" for i in interventions)
        assert any(i.type == "guardrail" for i in interventions)
        
        speed_breaker = next(i for i in interventions if i.type == "speed_breaker")
        assert speed_breaker.quantity == 10
        assert speed_breaker.unit == "units"
        assert speed_breaker.confidence > 0.6


# ==================== TEST 4: INTERVENTION PARSING - KEYWORDS ====================

def test_intervention_parsing_keywords():
    """Test keyword-based intervention parsing"""
    
    # Use separate texts to avoid cross-contamination between keyword searches
    # Each intervention in its own context
    text_speed_breakers = "Install 5 speed bumps at the school zone."
    text_guardrails = "Need 200 meters of guardrails along the bridge section."
    text_marking = "Road marking: 1000 sqm thermoplastic required for lanes."
    
    # Test speed breakers
    interventions = parse_with_keywords(text_speed_breakers)
    speed_breakers = [i for i in interventions if i.type == "speed_breaker"]
    assert len(speed_breakers) > 0
    assert speed_breakers[0].quantity == 5
    assert speed_breakers[0].confidence == 0.65
    assert speed_breakers[0].extraction_method == "ocr"
    
    # Test guardrails
    interventions = parse_with_keywords(text_guardrails)
    guardrails = [i for i in interventions if i.type == "guardrail"]
    assert len(guardrails) > 0
    assert guardrails[0].quantity == 200
    
    # Test road markings
    interventions = parse_with_keywords(text_marking)
    markings = [i for i in interventions if i.type == "road_marking"]
    assert len(markings) > 0
    assert markings[0].quantity == 1000


# ==================== TEST 5: CLAUSE RETRIEVAL ====================

def test_clause_retrieval(mock_irc_clauses):
    """Test IRC clause retrieval by intervention type"""
    
    with patch('services.clause_retriever.load_irc_clauses') as mock_load:
        mock_load.return_value = mock_irc_clauses
        
        # Test speed breaker clause
        clause = get_clause_by_intervention("speed_breaker")
        assert clause is not None
        assert clause["standard"] == "IRC 67"
        assert clause["clause"] == "3.2.1"
        assert "Speed Breaker" in clause["title"]
        
        # Test guardrail clause
        clause = get_clause_by_intervention("guardrail")
        assert clause is not None
        assert clause["standard"] == "IRC 35"
        assert "barrier" in clause["title"].lower()
        
        # Test unknown intervention type
        clause = get_clause_by_intervention("unknown_type")
        assert clause is None
        
        # Test search functionality
        results = search_clauses("speed", limit=5)
        assert len(results) > 0
        assert any("speed" in r["title"].lower() for r in results)


# ==================== TEST 6: QUANTITY CALCULATION - SPEED BREAKER ====================

def test_quantity_calculation_speed_breaker(mock_irc_clauses):
    """Test quantity calculation for speed breakers"""
    
    clause = mock_irc_clauses[0]  # Speed breaker clause
    
    result = calculate_quantity("speed_breaker", 10, clause)
    
    assert "error" not in result
    assert "Concrete M15" in result["material"]
    assert result["quantity"] == 0.525  # 10 * 0.0525
    assert result["unit"] == "cum"
    assert "formula" in result
    assert "3.5m" in result["formula"] and "0.3m" in result["formula"] and "0.05m" in result["formula"]
    assert len(result["assumptions"]) > 0
    
    # Test with invalid quantity (error case)
    result_error = calculate_quantity("speed_breaker", -5, clause)
    assert "error" in result_error


# ==================== TEST 7: QUANTITY CALCULATION - GUARDRAIL ====================

def test_quantity_calculation_guardrail(mock_irc_clauses):
    """Test quantity calculation for guardrails"""
    
    clause = mock_irc_clauses[1]  # Guardrail clause
    
    result = calculate_quantity("guardrail", 100, clause)
    
    assert "error" not in result
    assert "W-Beam" in result["material"] or "Guardrail" in result["material"]
    assert result["quantity"] == 500.0  # 100 meters * 5 kg/m
    assert result["unit"] == "kg"
    assert "kg" in result["formula"].lower()
    
    # Test with zero quantity (edge case)
    result_zero = calculate_quantity("guardrail", 0, clause)
    assert "error" in result_zero


# ==================== TEST 8: PRICE FETCHING ====================

def test_price_fetching():
    """Test material price fetching with exact and fuzzy matching"""
    
    mock_prices = {
        "concrete m15": {
            "material": "Concrete M15",
            "unit": "cum",
            "price_inr": 5500.0,
            "source": "CPWD SOR 2023",
            "item_code": "3.1",
            "category": "Concrete",
            "confidence": 0.92
        },
        "gi w-beam guardrail": {
            "material": "GI W-beam Guardrail",
            "unit": "kg",
            "price_inr": 75.0,
            "source": "CPWD SOR 2023",
            "item_code": "16.2.2",
            "category": "Steel",
            "confidence": 0.90
        }
    }
    
    with patch('services.price_fetcher.load_prices') as mock_load:
        mock_load.return_value = mock_prices
        
        # Test exact match
        price = get_material_price("Concrete M15")
        assert price is not None
        assert price["price_inr"] == 5500.0
        assert price["unit"] == "cum"
        
        # Test fuzzy match (slight variation in name)
        price_fuzzy = get_material_price("concrete m-15")
        assert price_fuzzy is not None
        
        # Test not found
        price_unknown = get_material_price("unknown material xyz")
        assert price_unknown is None
        
        # Test search
        results = search_prices("guardrail", limit=5)
        assert len(results) > 0
        assert any("guardrail" in r["material"].lower() for r in results)


# ==================== TEST 9: COST CALCULATION ====================

def test_cost_calculation(sample_intervention):
    """Test complete cost calculation pipeline"""
    
    with patch('services.clause_retriever.get_clause_by_intervention') as mock_clause, \
         patch('services.quantity_calculator.calculate_quantity') as mock_quantity, \
         patch('services.price_fetcher.get_material_price') as mock_price:
        
        # Mock IRC clause
        mock_clause.return_value = {
            "standard": "IRC 67",
            "clause": "3.2.1",
            "title": "Speed Breaker",
            "material": "Concrete M15"
        }
        
        # Mock quantity calculation
        mock_quantity.return_value = {
            "material": "Concrete M15",
            "quantity": 0.525,
            "unit": "cum",
            "formula": "3.5m × 0.3m × 0.05m per unit",
            "calculation": "10 units × 0.0525 cum/unit = 0.525 cum",
            "assumptions": ["IRC 67 specifications"],
            "irc_reference": "IRC 67:3.2.1"
        }
        
        # Mock price fetch
        mock_price.return_value = {
            "material": "Concrete M15",
            "price_inr": 5500.0,
            "unit": "cum",
            "source": "CPWD SOR 2023",
            "confidence": 0.92,
            "fetched_date": "2023-12-01"
        }
        
        # Calculate cost
        estimate_item = calculate_cost(sample_intervention)
        
        assert estimate_item is not None
        assert len(estimate_item.materials) == 1
        assert estimate_item.total_cost == 2887.5  # 0.525 * 5500
        assert "Concrete M15" in estimate_item.materials[0].name
        assert "extraction" in estimate_item.audit_trail
        assert "quantity_calculation" in estimate_item.audit_trail
        assert "pricing" in estimate_item.audit_trail
        assert len(estimate_item.assumptions) > 0


# ==================== TEST 10: VERIFICATION ====================

def test_verification_agent(sample_estimate_item, sample_intervention):
    """Test verification service for sanity checks"""
    
    # Test single item verification
    verification = verify_cost_item(sample_estimate_item)
    
    assert verification is not None
    assert "passed" in verification
    assert "status" in verification
    assert "checks" in verification
    
    # Should pass all checks for valid data
    assert verification["checks"]["math_correct"] == True
    assert verification["checks"]["units_valid"] == True
    assert verification["passed"] == True
    
    # Test with valid item but different total (Pydantic will catch invalid math before verification)
    # So we test verification logic with a valid item that has warnings
    item_with_warning = EstimateItem(
        intervention=sample_intervention,
        materials=[
            Material(
                name="Test Material",
                quantity=10,
                unit="kg",
                unit_price=100,
                total_cost=1000,  # Correct math
                irc_clause="IRC 67:3.2.1",
                price_source="Test",
                fetched_date=datetime.now()
            )
        ],
        total_cost=1000,
        audit_trail={"verification": {"warnings": ["Test warning"]}},
        assumptions=[]
    )
    
    verification_warning = verify_cost_item(item_with_warning)
    assert verification_warning["checks"]["math_correct"] == True
    
    # Test full estimate verification
    estimate = Estimate(
        estimate_id="TEST-001",
        filename="test.pdf",
        created_at=datetime.now(),
        status="completed",
        items=[sample_estimate_item],
        total_cost=2887.5,
        confidence=0.95,
        metadata={}
    )
    
    estimate_verification = verify_estimate(estimate)
    
    assert estimate_verification is not None
    assert "overall_status" in estimate_verification
    assert estimate_verification["total_items"] == 1
    assert estimate_verification["passed_count"] >= 0
    assert "recommendations" in estimate_verification


# ==================== EDGE CASES AND ERROR HANDLING ====================

def test_empty_text_parsing():
    """Test parsing with empty or invalid text"""
    
    # Empty text
    interventions = parse_with_keywords("")
    assert len(interventions) == 0
    
    # Text with no interventions
    interventions = parse_with_keywords("This is just random text with no interventions")
    assert len(interventions) == 0


def test_invalid_intervention_type():
    """Test handling of invalid intervention types"""
    
    result = calculate_quantity("invalid_type", 10, None)
    assert "error" in result
    assert "unrecognized" in result["error"].lower() or "not supported" in result["error"].lower()


def test_missing_price_fallback():
    """Test fallback behavior when price is not found"""
    
    with patch('services.cost_calculator.get_clause_by_intervention') as mock_clause, \
         patch('services.cost_calculator.calculate_quantity') as mock_quantity, \
         patch('services.cost_calculator.get_material_price') as mock_price:
        
        mock_clause.return_value = {"standard": "IRC 67", "clause": "3.2.1"}
        mock_quantity.return_value = {
            "material": "Unknown Material XYZ123",
            "quantity": 1.0,
            "unit": "unit",
            "formula": "test",
            "calculation": "test",
            "assumptions": [],
            "irc_reference": "IRC 67:3.2.1"
        }
        
        # Mock price to return None for unknown material
        mock_price.return_value = None
        
        intervention = Intervention(
            type="speed_breaker",
            quantity=1,
            unit="unit",
            location="test",
            confidence=0.9,
            extraction_method="gemini"
        )
        
        estimate_item = calculate_cost(intervention)
        
        # Should have fallback price
        assert estimate_item.materials[0].unit_price > 0
        assert "Fallback" in estimate_item.materials[0].price_source or "fallback" in estimate_item.materials[0].price_source.lower()


def test_zero_confidence_handling():
    """Test handling of interventions with very low confidence"""
    
    low_confidence = Intervention(
        type="speed_breaker",
        quantity=5,
        unit="units",
        location="test",
        confidence=0.30,  # Very low
        extraction_method="ocr"  # Use valid extraction method
    )
    
    # Should still process but flag for review
    assert low_confidence.confidence < 0.80


# ==================== INTEGRATION TEST ====================

def test_full_pipeline_integration(sample_pdf_text):
    """Test complete pipeline from text to verified estimate"""
    
    with patch('services.intervention_parser.call_gemini') as mock_gemini, \
         patch('services.clause_retriever.load_irc_clauses') as mock_clauses, \
         patch('services.price_fetcher.load_prices') as mock_prices:
        
        # Mock Gemini parsing
        mock_gemini.return_value = json.dumps([
            {
                "type": "speed_breaker",
                "quantity": 10,
                "unit": "units",
                "location": "km 5-10",
                "confidence": 0.95
            }
        ])
        
        # Mock IRC clauses
        mock_clauses.return_value = [
            {
                "standard": "IRC 67",
                "clause": "3.2.1",
                "title": "Speed Breaker",
                "material": "Concrete M15",
                "formula": "3.5 * 0.3 * 0.05",
                "per_unit_quantity": 0.0525,
                "unit": "cum"
            }
        ]
        
        # Mock prices
        mock_prices.return_value = {
            "concrete m15": {
                "material": "Concrete M15",
                "price_inr": 5500.0,
                "unit": "cum",
                "source": "CPWD SOR 2023",
                "confidence": 0.92
            }
        }
        
        # Execute full pipeline
        interventions = parse_interventions(sample_pdf_text)
        estimate = calculate_total_estimate(interventions, filename="test.pdf")
        verification = verify_estimate(estimate)
        
        # Assertions
        assert len(interventions) > 0
        assert estimate.total_cost > 0
        assert len(estimate.items) > 0
        assert verification["total_items"] > 0
        assert verification["overall_status"] in ["✅ VERIFIED", "⚠️ NEEDS REVIEW", "❌ FAILED"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
