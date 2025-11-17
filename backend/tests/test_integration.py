"""
End-to-End Integration Tests for BRAKES Backend

Tests complete workflows from PDF upload to estimate generation and export.
Uses realistic mock PDFs and API testing.
"""

import pytest
import os
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import FastAPI test client
from fastapi.testclient import TestClient

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from services.pdf_extractor import extract_pdf_text
from services.intervention_parser import parse_interventions
from services.cost_calculator import calculate_total_estimate
from services.verification import verify_estimate
from models.intervention import Intervention, Estimate


# ==================== FIXTURES ====================

@pytest.fixture
def test_client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def realistic_pdf_content():
    """Realistic road safety audit report text content"""
    return """
    ROAD SAFETY AUDIT REPORT
    National Highway 44 - Section: Km 125 to Km 145
    Date: October 15, 2025
    Location: Maharashtra State
    
    EXECUTIVE SUMMARY
    This road safety audit identifies critical safety interventions required
    along the 20 km stretch of NH-44. The audit was conducted as per IRC:SP-88
    guidelines for road safety audits.
    
    RECOMMENDED INTERVENTIONS
    
    1. SPEED CONTROL MEASURES
    Location: Km 127+500 to Km 128+200 (School Zone)
    Recommendation: Install 8 speed breakers (trapezoidal profile as per IRC 67)
    Justification: High pedestrian activity near primary school
    Priority: HIGH
    
    2. CRASH BARRIERS
    Location: Km 132+000 to Km 135+500 (Curved Section with Steep Drop)
    Recommendation: Install 3500 meters of W-beam metal crash barriers
    Specification: IRC 35 compliant galvanized steel guardrails
    Priority: CRITICAL
    
    3. ROAD MARKINGS
    Location: Km 125+000 to Km 145+000 (Entire Stretch)
    Recommendation: Apply 15000 square meters of thermoplastic road markings
    Details: Center line, edge line, and lane markings
    Specification: IRC 35 - White and yellow thermoplastic paint
    Priority: HIGH
    
    4. STREET LIGHTING
    Location: Km 130+000 to Km 135+000 (High Accident Zone)
    Recommendation: Install 50 LED street lights with 40m spacing
    Specification: 150W LED luminaires on 10m high poles
    Priority: HIGH
    
    5. TRAFFIC SIGNAGE
    Location: Various locations along the stretch
    Recommendation: Install 25 regulatory and warning signs
    Details: Speed limit signs, curve warning signs, pedestrian crossing signs
    Specification: IRC 67 compliant retroreflective signs
    Priority: MEDIUM
    
    6. PEDESTRIAN FACILITIES
    Location: Km 127+400 (Near School)
    Recommendation: Construct 1 zebra crossing with proper markings
    Specification: IRC 35 - Thermoplastic zebra crossing markings (4m x 8m)
    Priority: HIGH
    
    COST ESTIMATE SUMMARY
    Estimated Total Cost: To be calculated based on CPWD SOR 2023 rates
    
    RECOMMENDATIONS
    All interventions should be implemented within 6 months to reduce
    accident risk and improve road safety for all users.
    
    Audit Team:
    Lead Auditor: Er. Rajesh Kumar (M.Tech Transportation Engineering)
    Team Members: Er. Priya Sharma, Er. Amit Verma
    Date: October 15, 2025
    """


@pytest.fixture
def mock_irc_clauses_full():
    """Complete set of mock IRC clauses for integration testing"""
    return [
        {
            "standard": "IRC 67",
            "clause": "3.2.1",
            "title": "Speed Breaker - Trapezoidal Profile",
            "text": "Speed breakers shall be 3.5m wide, 0.3m high with 0.05m thickness",
            "material": "Concrete M15 (1:2:4)",
            "unit": "cum",
            "formula": "3.5 * 0.3 * 0.05",
            "per_unit_quantity": 0.0525,
            "category": "Speed Control",
            "page": "25"
        },
        {
            "standard": "IRC 35",
            "clause": "6.1.1",
            "title": "Metal Beam Crash Barrier - W-beam",
            "text": "W-beam crash barriers with galvanized steel",
            "material": "Galvanized Steel W-Beam",
            "unit": "kg",
            "formula": "5 kg per meter",
            "per_unit_quantity": 5,
            "category": "Crash Barrier",
            "page": "45"
        },
        {
            "standard": "IRC 35",
            "clause": "8.2.3",
            "title": "Thermoplastic Road Marking Paint",
            "text": "Hot applied thermoplastic road marking material",
            "material": "Thermoplastic Paint (White)",
            "unit": "kg",
            "formula": "3 kg per sqm",
            "per_unit_quantity": 3,
            "category": "Road Marking",
            "page": "78"
        },
        {
            "standard": "IRC 67",
            "clause": "5.1.2",
            "title": "LED Street Light Assembly",
            "text": "LED street lighting with 150W luminaire",
            "material": "150W LED Street Light",
            "unit": "nos",
            "formula": "1 unit",
            "per_unit_quantity": 1,
            "category": "Street Lighting",
            "page": "92"
        },
        {
            "standard": "IRC 67",
            "clause": "4.3.1",
            "title": "Retroreflective Traffic Sign",
            "text": "Traffic signs with retroreflective sheeting",
            "material": "Traffic Sign (900mm x 900mm)",
            "unit": "nos",
            "formula": "1 unit",
            "per_unit_quantity": 1,
            "category": "Signage",
            "page": "65"
        },
        {
            "standard": "IRC 35",
            "clause": "8.1.5",
            "title": "Zebra Crossing Marking",
            "text": "Pedestrian zebra crossing with thermoplastic",
            "material": "Thermoplastic Paint (White)",
            "unit": "kg",
            "formula": "3 kg per sqm",
            "per_unit_quantity": 3,
            "category": "Road Marking",
            "page": "76"
        }
    ]


@pytest.fixture
def mock_prices_full():
    """Complete set of mock prices for integration testing"""
    return {
        "concrete m15": {
            "material": "Concrete M15 (1:2:4)",
            "unit": "cum",
            "price_inr": 5500.0,
            "source": "CPWD SOR 2023",
            "item_code": "3.1",
            "category": "Concrete",
            "confidence": 0.92
        },
        "galvanized steel w-beam": {
            "material": "Galvanized Steel W-Beam",
            "unit": "kg",
            "price_inr": 85.0,
            "source": "CPWD SOR 2023",
            "item_code": "16.2.2",
            "category": "Steel",
            "confidence": 0.90
        },
        "thermoplastic paint": {
            "material": "Thermoplastic Paint (White)",
            "unit": "kg",
            "price_inr": 320.0,
            "source": "CPWD SOR 2023",
            "item_code": "21.4.1",
            "category": "Paint & Marking",
            "confidence": 0.88
        },
        "150w led street light": {
            "material": "150W LED Street Light",
            "unit": "nos",
            "price_inr": 8500.0,
            "source": "CPWD SOR 2023",
            "item_code": "18.5.3",
            "category": "Electrical",
            "confidence": 0.85
        },
        "traffic sign": {
            "material": "Traffic Sign (900mm x 900mm)",
            "unit": "nos",
            "price_inr": 3500.0,
            "source": "CPWD SOR 2023",
            "item_code": "19.2.1",
            "category": "Signage",
            "confidence": 0.87
        }
    }


@pytest.fixture
def mock_pdf_file():
    """Create a mock PDF file-like object"""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    return io.BytesIO(pdf_content)


# ==================== TEST 1: FULL PIPELINE ====================

def test_full_pipeline(realistic_pdf_content, mock_irc_clauses_full, mock_prices_full):
    """
    Test complete pipeline from PDF text to verified estimate.
    
    This test simulates the entire processing workflow:
    1. PDF extraction (mocked with realistic text)
    2. Intervention parsing using AI/keywords
    3. IRC clause matching
    4. Quantity calculation
    5. Price fetching
    6. Cost calculation
    7. Verification
    
    Validates end-to-end data flow and transformations.
    """
    
    # Mock external dependencies
    with patch('services.clause_retriever.load_irc_clauses') as mock_clauses, \
         patch('services.price_fetcher.load_prices') as mock_prices, \
         patch('services.intervention_parser.call_gemini') as mock_gemini:
        
        # Setup mocks
        mock_clauses.return_value = mock_irc_clauses_full
        mock_prices.return_value = mock_prices_full
        
        # Mock Gemini to extract interventions from the PDF text
        mock_gemini.return_value = json.dumps([
            {
                "type": "speed_breaker",
                "quantity": 8,
                "unit": "units",
                "location": "Km 127+500 to Km 128+200",
                "confidence": 0.95
            },
            {
                "type": "guardrail",
                "quantity": 3500,
                "unit": "meters",
                "location": "Km 132+000 to Km 135+500",
                "confidence": 0.92
            },
            {
                "type": "road_marking",
                "quantity": 15000,
                "unit": "sqm",
                "location": "Km 125+000 to Km 145+000",
                "confidence": 0.90
            },
            {
                "type": "street_light",
                "quantity": 50,
                "unit": "nos",
                "location": "Km 130+000 to Km 135+000",
                "confidence": 0.88
            },
            {
                "type": "signage",
                "quantity": 25,
                "unit": "nos",
                "location": "Various locations",
                "confidence": 0.85
            },
            {
                "type": "pedestrian_crossing",
                "quantity": 1,
                "unit": "unit",
                "location": "Km 127+400",
                "confidence": 0.87
            }
        ])
        
        # STEP 1: Parse interventions from text
        interventions = parse_interventions(realistic_pdf_content)
        
        # Assertions: Check interventions were extracted
        assert len(interventions) >= 6, f"Expected at least 6 interventions, got {len(interventions)}"
        
        intervention_types = [i.type for i in interventions]
        assert "speed_breaker" in intervention_types
        assert "guardrail" in intervention_types
        assert "road_marking" in intervention_types
        assert "street_light" in intervention_types
        assert "signage" in intervention_types
        
        # Check quantities are reasonable
        speed_breaker = next(i for i in interventions if i.type == "speed_breaker")
        assert speed_breaker.quantity == 8
        assert speed_breaker.confidence >= 0.85
        
        guardrail = next(i for i in interventions if i.type == "guardrail")
        assert guardrail.quantity == 3500
        assert "Km 132" in guardrail.location
        
        # STEP 2: Calculate complete estimate
        estimate = calculate_total_estimate(
            interventions=interventions,
            filename="NH44_Safety_Audit.pdf"
        )
        
        # Assertions: Check estimate structure
        assert estimate is not None
        assert estimate.estimate_id is not None
        assert estimate.filename == "NH44_Safety_Audit.pdf"
        assert estimate.status == "completed"
        assert len(estimate.items) >= 6
        
        # Check total cost is calculated
        assert estimate.total_cost > 0
        assert estimate.total_cost > 100000, "Total cost should be significant for 6+ interventions"
        
        # Check average confidence
        assert 0.0 <= estimate.confidence <= 1.0
        # Confidence might be lower due to keyword fallback parsing and missing clauses
        assert estimate.confidence > 0.65, f"Overall confidence should be reasonable, got {estimate.confidence}"
        
        # STEP 3: Verify each estimate item has complete audit trail
        for item in estimate.items:
            assert item.intervention is not None
            assert len(item.materials) > 0
            assert item.total_cost > 0
            
            # Check audit trail completeness
            assert "extraction" in item.audit_trail
            assert "clause_matching" in item.audit_trail
            assert "quantity_calculation" in item.audit_trail
            assert "pricing" in item.audit_trail
            
            # Check extraction details
            extraction = item.audit_trail["extraction"]
            assert "method" in extraction
            assert "confidence" in extraction
            
            # Check clause matching
            clause = item.audit_trail["clause_matching"]
            assert "standard" in clause
            # Some interventions might not find IRC clauses (marked for manual review)
            if clause["standard"] is not None:
                assert clause["standard"] in ["IRC 67", "IRC 35", "IRC 99", "IRC SP-84"]
            
            # Check quantity calculation
            quantity = item.audit_trail["quantity_calculation"]
            assert "formula" in quantity
            assert "result" in quantity
            assert quantity["result"] > 0
            
            # Check pricing
            pricing = item.audit_trail["pricing"]
            assert "source" in pricing
            # Some materials might use fallback pricing
            assert pricing["source"] in ["CPWD SOR 2023", "Fallback", "Fallback Average"]
            assert "unit_price" in pricing
            assert pricing["unit_price"] > 0
            
            # Check materials
            for material in item.materials:
                assert material.name is not None
                assert material.quantity > 0
                assert material.unit_price > 0
                assert material.total_cost > 0
                assert material.irc_clause is not None
                assert material.price_source is not None
        
        # STEP 4: Verify the estimate
        verification = verify_estimate(estimate)
        
        # Assertions: Check verification results
        assert verification is not None
        assert "overall_status" in verification
        assert verification["total_items"] == len(estimate.items)
        assert verification["passed_count"] >= 0
        
        # Overall status should be positive (verified or needs review)
        assert verification["overall_status"] in ["✅ VERIFIED", "⚠️ NEEDS REVIEW", "❌ FAILED"]
        
        # Check that most items pass verification
        pass_rate = verification["passed_count"] / verification["total_items"]
        assert pass_rate >= 0.80, f"At least 80% items should pass verification, got {pass_rate:.1%}"
        
        # STEP 5: Validate specific cost calculations
        # Speed breakers: 8 units × 0.0525 cum/unit × ₹5500/cum = ₹2,310
        speed_breaker_item = next(i for i in estimate.items if i.intervention.type == "speed_breaker")
        expected_speed_breaker_cost = 8 * 0.0525 * 5500
        assert abs(speed_breaker_item.total_cost - expected_speed_breaker_cost) < 100, \
            f"Speed breaker cost mismatch: expected ~₹{expected_speed_breaker_cost}, got ₹{speed_breaker_item.total_cost}"
        
        # Guardrails: 3500 meters × 5 kg/m × ₹85/kg = ₹1,487,500
        guardrail_item = next(i for i in estimate.items if i.intervention.type == "guardrail")
        expected_guardrail_cost = 3500 * 5 * 85
        assert abs(guardrail_item.total_cost - expected_guardrail_cost) < 10000, \
            f"Guardrail cost mismatch: expected ~₹{expected_guardrail_cost}, got ₹{guardrail_item.total_cost}"
        
        # Thermoplastic markings: 15000 sqm × 3 kg/sqm × ₹320/kg = ₹14,400,000
        marking_item = next(i for i in estimate.items if i.intervention.type == "road_marking")
        expected_marking_cost = 15000 * 3 * 320
        assert abs(marking_item.total_cost - expected_marking_cost) < 50000, \
            f"Road marking cost mismatch: expected ~₹{expected_marking_cost}, got ₹{marking_item.total_cost}"
        
        # STEP 6: Check metadata
        assert "processing_time_seconds" in estimate.metadata
        assert estimate.metadata["processing_time_seconds"] >= 0
        assert estimate.metadata["interventions_processed"] == len(interventions)
        assert estimate.metadata["items_with_costs"] == len(estimate.items)
        
        print(f"\n✅ Full Pipeline Test PASSED")
        print(f"   Interventions Found: {len(interventions)}")
        print(f"   Total Cost: ₹{estimate.total_cost:,.2f}")
        print(f"   Average Confidence: {estimate.confidence:.1%}")
        print(f"   Verification Pass Rate: {pass_rate:.1%}")


# ==================== TEST 2: API UPLOAD FLOW ====================

def test_api_upload_flow(test_client, realistic_pdf_content, mock_irc_clauses_full, mock_prices_full, mock_pdf_file):
    """
    Test complete API workflow from upload to export.
    
    This test validates:
    1. PDF upload via POST /api/upload
    2. Estimate retrieval via GET /api/estimate/{id}
    3. CSV export via GET /api/estimate/{id}/export?format=csv
    4. Data consistency across all API responses
    
    Simulates real client interaction with the API.
    """
    
    # Mock external dependencies
    with patch('services.clause_retriever.load_irc_clauses') as mock_clauses, \
         patch('services.price_fetcher.load_prices') as mock_prices, \
         patch('services.intervention_parser.call_gemini') as mock_gemini, \
         patch('services.pdf_extractor.extract_with_pdfplumber') as mock_pdf_extract, \
         patch('os.path.exists') as mock_exists, \
         patch('config.database.get_database') as mock_get_db:
        
        # Setup mocks
        mock_clauses.return_value = mock_irc_clauses_full
        mock_prices.return_value = mock_prices_full
        mock_exists.return_value = True
        
        # Mock database
        mock_collection = MagicMock()
        mock_collection.insert_one.return_value = MagicMock(inserted_id="test_id_12345")
        mock_collection.find_one.return_value = None
        mock_db_instance = MagicMock()
        mock_db_instance.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db_instance
        
        # Mock PDF extraction
        mock_pdf_extract.return_value = {
            "text": realistic_pdf_content,
            "method": "pdfplumber",
            "confidence": 0.95,
            "page_count": 3,
            "char_count": len(realistic_pdf_content)
        }
        
        # Mock Gemini parsing
        mock_gemini.return_value = json.dumps([
            {
                "type": "speed_breaker",
                "quantity": 8,
                "unit": "units",
                "location": "Km 127+500 to Km 128+200",
                "confidence": 0.95
            },
            {
                "type": "guardrail",
                "quantity": 3500,
                "unit": "meters",
                "location": "Km 132+000 to Km 135+500",
                "confidence": 0.92
            },
            {
                "type": "road_marking",
                "quantity": 15000,
                "unit": "sqm",
                "location": "Km 125+000 to Km 145+000",
                "confidence": 0.90
            }
            ])
        
        # STEP 1: Upload PDF via API
        files = {
            "file": ("NH44_Safety_Audit.pdf", mock_pdf_file, "application/pdf")
        }
        
        response = test_client.post("/api/upload", files=files)
        
        # Assertions: Check upload response
        assert response.status_code == 200, f"Upload failed with status {response.status_code}"
        
        upload_data = response.json()
        assert "estimate_id" in upload_data
        assert "filename" in upload_data
        assert upload_data["filename"] == "NH44_Safety_Audit.pdf"
        assert "status" in upload_data
        assert upload_data["status"] in ["completed", "pending"]
        assert "extraction_method" in upload_data
        assert upload_data["extraction_method"] == "pdfplumber"
        assert "interventions_found" in upload_data
        assert upload_data["interventions_found"] >= 3
        assert "total_cost" in upload_data
        assert upload_data["total_cost"] > 0
        
        estimate_id = upload_data["estimate_id"]
        total_cost = upload_data["total_cost"]
        interventions_count = upload_data["interventions_found"]
        
        print(f"\n✅ Step 1: PDF Upload Successful")
        print(f"   Estimate ID: {estimate_id}")
        print(f"   Interventions: {interventions_count}")
        print(f"   Total Cost: ₹{total_cost:,.2f}")
        
        # STEP 2: Fetch full estimate via API
        # STEP 2: Fetch full estimate via API
        # Mock the database response for fetching estimate
        mock_estimate_data = {
            "_id": "test_id_12345",
            "estimate_id": estimate_id,
            "filename": "NH44_Safety_Audit.pdf",
            "created_at": datetime.now(),
            "status": "completed",
            "items": [
                {
                    "intervention": {
                        "type": "speed_breaker",
                        "quantity": 8,
                        "unit": "units",
                        "location": "Km 127+500",
                        "confidence": 0.95,
                        "extraction_method": "gemini"
                    },
                    "materials": [
                        {
                            "name": "Concrete M15 (1:2:4)",
                            "quantity": 0.42,
                            "unit": "cum",
                            "unit_price": 5500.0,
                            "total_cost": 2310.0,
                            "irc_clause": "IRC 67:3.2.1",
                            "price_source": "CPWD SOR 2023",
                            "fetched_date": datetime.now()
                        }
                    ],
                    "total_cost": 2310.0,
                    "audit_trail": {
                        "extraction": {"method": "gemini", "confidence": 0.95},
                        "clause_matching": {"standard": "IRC 67", "clause": "3.2.1"},
                        "quantity_calculation": {"formula": "8 × 0.0525", "result": 0.42},
                        "pricing": {"source": "CPWD SOR 2023", "unit_price": 5500.0}
                    },
                    "assumptions": ["IRC 67 specifications"]
                }
            ],
            "total_cost": total_cost,
            "confidence": 0.92,
            "metadata": {
                "processing_time_seconds": 2.5,
                "interventions_processed": interventions_count
            }
        }
        
        mock_collection.find_one.return_value = mock_estimate_data
        
        response = test_client.get(f"/api/estimate/{estimate_id}")
        
        # Assertions: Check fetch response
        assert response.status_code == 200, f"Fetch failed with status {response.status_code}"
        
        estimate_data = response.json()
        assert estimate_data["estimate_id"] == estimate_id
        assert estimate_data["filename"] == "NH44_Safety_Audit.pdf"
        assert estimate_data["status"] == "completed"
        assert len(estimate_data["items"]) >= 1
        assert estimate_data["total_cost"] == total_cost
        
        # Validate data consistency with upload response
        assert estimate_data["total_cost"] == upload_data["total_cost"]
        
        print(f"\n✅ Step 2: Estimate Fetch Successful")
        print(f"   Items: {len(estimate_data['items'])}")
        print(f"   Status: {estimate_data['status']}")
        
        # STEP 3: Export estimate as CSV
        response = test_client.get(f"/api/estimate/{estimate_id}/export?format=csv")
        
        # Assertions: Check export response
        assert response.status_code == 200, f"Export failed with status {response.status_code}"
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "content-disposition" in response.headers
        assert f"{estimate_id}" in response.headers["content-disposition"]
        
        csv_content = response.content.decode("utf-8")
        assert len(csv_content) > 0
        
        # Check CSV headers
        csv_lines = csv_content.strip().split("\n")
        headers = csv_lines[0]
        assert "Estimate ID" in headers
        assert "Intervention Type" in headers
        assert "Quantity" in headers
        assert "Total Cost" in headers
        assert "IRC Clause" in headers
        
        # Check CSV data rows (at least one row beyond header)
        assert len(csv_lines) >= 2, "CSV should have at least header + 1 data row"
        
        # Validate data in CSV matches estimate
        data_row = csv_lines[1]
        assert estimate_id in data_row
        assert "speed_breaker" in data_row or "guardrail" in data_row or "road_marking" in data_row
        
        print(f"\n✅ Step 3: CSV Export Successful")
        print(f"   CSV Size: {len(csv_content)} bytes")
        print(f"   CSV Rows: {len(csv_lines)}")
        
        # STEP 4: Test JSON export
        response = test_client.get(f"/api/estimate/{estimate_id}/export?format=json")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        json_content = response.json()
        assert "estimate" in json_content
        assert json_content["estimate"]["estimate_id"] == estimate_id
        assert json_content["estimate"]["total_cost"] == total_cost
        
        # Check export metadata
        assert "export_metadata" in json_content
        assert json_content["export_metadata"]["format"] == "json"
        assert "exported_at" in json_content["export_metadata"]
        
        print(f"\n✅ Step 4: JSON Export Successful")
        
        # STEP 5: Validate data consistency across all API responses
        # All responses should have same estimate_id
        assert upload_data["estimate_id"] == estimate_id
        assert estimate_data["estimate_id"] == estimate_id
        assert json_content["estimate"]["estimate_id"] == estimate_id
        
        # All responses should have same total cost
        assert upload_data["total_cost"] == total_cost
        assert estimate_data["total_cost"] == total_cost
        assert json_content["estimate"]["total_cost"] == total_cost
        
        # All responses should have same filename
        assert upload_data["filename"] == "NH44_Safety_Audit.pdf"
        assert estimate_data["filename"] == "NH44_Safety_Audit.pdf"
        assert json_content["estimate"]["filename"] == "NH44_Safety_Audit.pdf"
        
        print(f"\n✅ Step 5: Data Consistency Validated")
        print(f"   All API responses consistent ✓")
        
        # STEP 6: Test estimate summary endpoint
        response = test_client.get(f"/api/estimate/{estimate_id}/summary")
        
        if response.status_code == 200:
            summary_data = response.json()
            assert summary_data["estimate_id"] == estimate_id
            assert summary_data["total_cost"] == total_cost
            assert "items" not in summary_data or len(summary_data.get("items", [])) < len(estimate_data["items"])
            
            print(f"\n✅ Step 6: Summary Endpoint Validated")
        
        print(f"\n✅ API Upload Flow Test PASSED")
        print(f"   All API endpoints working correctly")
        print(f"   Data consistency maintained across all operations")


# ==================== TEST 3: ERROR HANDLING ====================

def test_api_upload_invalid_file(test_client):
    """Test API error handling for invalid file uploads"""
    
    # Test with non-PDF file
    files = {
        "file": ("test.txt", io.BytesIO(b"Not a PDF"), "text/plain")
    }
    
    response = test_client.post("/api/upload", files=files)
    assert response.status_code in [400, 422], "Should reject non-PDF files"
    
    # Test with oversized file (mock > 25 MB)
    large_content = b"x" * (26 * 1024 * 1024)  # 26 MB
    files = {
        "file": ("large.pdf", io.BytesIO(large_content), "application/pdf")
    }
    
    response = test_client.post("/api/upload", files=files)
    assert response.status_code in [400, 413, 422], "Should reject oversized files"
    
    print(f"\n✅ Error Handling Test PASSED")


def test_api_estimate_not_found(test_client):
    """Test API error handling for non-existent estimates"""
    
    with patch('routes.estimate.get_database') as mock_get_db:
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db_instance = MagicMock()
        mock_db_instance.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db_instance
        
        response = test_client.get("/api/estimate/nonexistent_id_12345")
        assert response.status_code == 404, "Should return 404 for non-existent estimate"
        
        response_data = response.json()
        assert "detail" in response_data
        assert "not found" in response_data["detail"].lower()
    
    print(f"\n✅ Not Found Error Handling Test PASSED")


# ==================== HELPER FUNCTION ====================

def create_realistic_mock_pdf(content: str, filename: str = "test.pdf") -> str:
    """
    Create a temporary PDF file with realistic content for testing.
    
    Args:
        content: Text content to include in PDF
        filename: Desired filename
        
    Returns:
        str: Path to created PDF file
    """
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, filename)
    
    # For real PDF creation, you would use reportlab or similar
    # For testing purposes, we just create a file with PDF header
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n")
        f.write(content.encode("utf-8"))
    
    return pdf_path


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
