"""
Upload Route - PDF File Upload and Processing

This module handles PDF file uploads, extraction, parsing, and cost estimation.
"""

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from config.database import get_database
from services.pdf_extractor import extract_pdf_text
from services.intervention_parser import parse_interventions
from services.cost_calculator import calculate_total_estimate
from services.verification import verify_estimate
from models.intervention import Intervention, Estimate

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Configuration
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in bytes
ALLOWED_EXTENSIONS = {".pdf"}
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def validate_file_size(file_size: int) -> None:
    """
    Validate that uploaded file size is within limits.
    
    Args:
        file_size: Size of the file in bytes
        
    Raises:
        HTTPException: If file is too large
    """
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {size_mb:.2f} MB. Maximum allowed: {max_mb} MB"
        )


def validate_file_type(filename: str) -> None:
    """
    Validate that uploaded file has allowed extension.
    
    Args:
        filename: Name of the uploaded file
        
    Raises:
        HTTPException: If file type is not allowed
    """
    file_extension = Path(filename).suffix.lower()
    
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file_extension}. Only PDF files are allowed."
        )


def cleanup_temp_file(file_path: Path) -> None:
    """
    Clean up temporary uploaded file.
    
    Args:
        file_path: Path to the temporary file
    """
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to clean up temporary file {file_path}: {str(e)}")


async def save_upload_file(upload_file: UploadFile) -> Path:
    """
    Save uploaded file to temporary location.
    
    Args:
        upload_file: FastAPI UploadFile object
        
    Returns:
        Path: Path to saved file
        
    Raises:
        HTTPException: If file save fails
    """
    try:
        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        file_extension = Path(upload_file.filename).suffix
        temp_filename = f"{timestamp}_{unique_id}{file_extension}"
        temp_path = UPLOAD_DIR / temp_filename
        
        # Save file
        logger.info(f"Saving uploaded file to {temp_path}")
        
        with temp_path.open("wb") as buffer:
            content = await upload_file.read()
            buffer.write(content)
        
        logger.info(f"File saved successfully: {temp_path} ({len(content)} bytes)")
        
        return temp_path
        
    except Exception as e:
        logger.error(f"Failed to save upload file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )


def save_estimate_to_db(estimate: Estimate) -> bool:
    """
    Save estimate to MongoDB.
    
    Args:
        estimate: Estimate object to save
        
    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        db = get_database()
        if db is None:
            logger.error("Database connection not available")
            return False
        
        collection = db["estimates"]
        
        # Convert Estimate to dict for MongoDB
        estimate_dict = estimate.model_dump()
        
        # Insert into database
        result = collection.insert_one(estimate_dict)
        
        logger.info(
            f"Estimate saved to database: {estimate.estimate_id} "
            f"(MongoDB ID: {result.inserted_id})"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to save estimate to database: {str(e)}")
        return False


def create_item_summary(estimate: Estimate) -> List[Dict[str, Any]]:
    """
    Create summary of estimate items for response.
    
    Args:
        estimate: Estimate object
        
    Returns:
        List of item summaries
    """
    items = []
    
    for item in estimate.items:
        items.append({
            "intervention_type": item.intervention.type,
            "quantity": item.intervention.quantity,
            "unit": item.intervention.unit,
            "location": item.intervention.location,
            "confidence": item.intervention.confidence,
            "total_cost": item.total_cost,
            "materials_count": len(item.materials),
            "warnings": item.audit_trail.get("verification", {}).get("warnings", [])
        })
    
    return items


@router.post("/upload", response_model=None)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> JSONResponse:
    """
    Upload PDF file for road safety intervention cost estimation.
    
    Pipeline:
    1. Validate file (size, type)
    2. Save temporarily
    3. Extract text from PDF
    4. Parse interventions
    5. Calculate costs for each intervention
    6. Verify calculations
    7. Save estimate to database
    8. Return summary
    
    Args:
        background_tasks: FastAPI background tasks
        file: Uploaded PDF file
        
    Returns:
        JSONResponse: Estimate summary with ID and costs
        
    Raises:
        HTTPException: Various errors (400, 413, 500)
    """
    start_time = time.time()
    temp_file_path = None
    
    logger.info(f"Received upload request: {file.filename}")
    
    try:
        # Step 1: Validate file type
        logger.debug("Step 1: Validating file type")
        validate_file_type(file.filename)
        
        # Step 2: Read file content and validate size
        logger.debug("Step 2: Reading and validating file size")
        file_content = await file.read()
        file_size = len(file_content)
        validate_file_size(file_size)
        
        logger.info(f"File validated: {file.filename} ({file_size / 1024:.2f} KB)")
        
        # Reset file pointer
        await file.seek(0)
        
        # Step 3: Save uploaded file temporarily
        logger.debug("Step 3: Saving file temporarily")
        temp_file_path = await save_upload_file(file)
        
        # Step 4: Extract text from PDF
        logger.debug("Step 4: Extracting text from PDF")
        extraction_result = extract_pdf_text(str(temp_file_path))
        
        if not extraction_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract text from PDF"
            )
        
        extracted_text = extraction_result.get("text", "")
        extraction_method = extraction_result.get("method", "unknown")
        extraction_confidence = extraction_result.get("confidence", 0.0)
        page_count = extraction_result.get("page_count", 0)
        
        logger.info(
            f"Text extracted: {len(extracted_text)} chars, "
            f"{page_count} pages, method: {extraction_method}"
        )
        
        # Check if text is empty
        if not extracted_text or len(extracted_text.strip()) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF appears to be empty or contains insufficient text content"
            )
        
        # Step 5: Parse interventions from text
        logger.debug("Step 5: Parsing interventions from text")
        interventions = parse_interventions(extracted_text)
        
        if not interventions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No road safety interventions found in the PDF. "
                       "Please ensure the document contains information about "
                       "speed breakers, guardrails, road markings, street lights, or road signs."
            )
        
        logger.info(f"Parsed {len(interventions)} interventions")
        
        # Step 6: Calculate costs for all interventions
        logger.debug("Step 6: Calculating costs for interventions")
        estimate = calculate_total_estimate(
            interventions=interventions,
            filename=file.filename
        )
        
        logger.info(
            f"Cost calculation complete: ₹{estimate.total_cost} "
            f"for {len(estimate.items)} items"
        )
        
        # Step 7: Verify calculations
        logger.debug("Step 7: Verifying calculations")
        verification_result = verify_estimate(estimate)
        
        logger.info(
            f"Verification complete: {verification_result['overall_status']} - "
            f"passed: {verification_result['passed_count']}, "
            f"warnings: {verification_result['warning_count']}, "
            f"errors: {verification_result['error_count']}"
        )
        
        # Add verification results to metadata
        estimate.metadata["verification"] = {
            "status": verification_result["overall_status"],
            "passed_count": verification_result["passed_count"],
            "warning_count": verification_result["warning_count"],
            "error_count": verification_result["error_count"],
            "recommendations": verification_result["recommendations"]
        }
        
        # Step 8: Save estimate to database
        logger.debug("Step 8: Saving estimate to database")
        saved = save_estimate_to_db(estimate)
        
        if not saved:
            logger.warning("Failed to save estimate to database, but continuing")
            estimate.metadata["database_save_failed"] = True
        
        # Calculate processing time
        processing_time = time.time() - start_time
        processing_time_ms = int(processing_time * 1000)
        
        logger.info(
            f"Upload processing complete: {estimate.estimate_id} "
            f"({processing_time_ms} ms)"
        )
        
        # Schedule cleanup of temporary file
        if temp_file_path:
            background_tasks.add_task(cleanup_temp_file, temp_file_path)
        
        # Create response
        response_data = {
            "success": True,
            "estimate_id": estimate.estimate_id,
            "filename": file.filename,
            "status": estimate.status,
            "extraction_method": extraction_method,
            "extraction_confidence": extraction_confidence,
            "interventions_found": len(interventions),
            "total_cost": estimate.total_cost,
            "overall_confidence": estimate.confidence,
            "processing_time_ms": processing_time_ms,
            "verification": {
                "status": verification_result["overall_status"],
                "passed_count": verification_result["passed_count"],
                "warning_count": verification_result["warning_count"],
                "error_count": verification_result["error_count"]
            },
            "metadata": {
                "page_count": page_count,
                "text_length": len(extracted_text),
                "items_with_costs": estimate.metadata.get("items_with_costs", 0),
                "requires_manual_review": estimate.metadata.get("requires_manual_review", False)
            },
            "items": create_item_summary(estimate)
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        if temp_file_path:
            background_tasks.add_task(cleanup_temp_file, temp_file_path)
        raise
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(
            f"Unexpected error during upload processing: {str(e)}",
            exc_info=True
        )
        
        # Clean up temp file
        if temp_file_path:
            background_tasks.add_task(cleanup_temp_file, temp_file_path)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing error: {str(e)}"
        )


@router.get("/upload/status/{estimate_id}", response_model=None)
async def get_upload_status(estimate_id: str) -> JSONResponse:
    """
    Get status of a previously uploaded estimate.
    
    Args:
        estimate_id: Estimate ID to query
        
    Returns:
        JSONResponse: Estimate status and summary
        
    Raises:
        HTTPException: If estimate not found
    """
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        collection = db["estimates"]
        
        # Find estimate
        estimate_doc = collection.find_one({"estimate_id": estimate_id})
        
        if not estimate_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Estimate not found: {estimate_id}"
            )
        
        # Remove MongoDB _id field
        if "_id" in estimate_doc:
            estimate_doc["_id"] = str(estimate_doc["_id"])
        
        # Create summary response
        response_data = {
            "success": True,
            "estimate_id": estimate_doc.get("estimate_id"),
            "filename": estimate_doc.get("filename"),
            "status": estimate_doc.get("status"),
            "total_cost": estimate_doc.get("total_cost"),
            "confidence": estimate_doc.get("confidence"),
            "created_at": estimate_doc.get("created_at"),
            "items_count": len(estimate_doc.get("items", [])),
            "metadata": estimate_doc.get("metadata", {})
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching estimate status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch estimate status: {str(e)}"
        )
