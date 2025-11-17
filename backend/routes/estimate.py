"""
Estimate Route - Estimate Retrieval and Management

This module handles estimate retrieval, listing, deletion, and export operations.
"""

import logging
import csv
import json
import io
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId

from config.database import get_database
from models.intervention import Estimate

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def serialize_estimate(estimate_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize estimate document for JSON response.
    
    Converts MongoDB ObjectId to string and formats dates.
    
    Args:
        estimate_doc: Raw MongoDB document
        
    Returns:
        Dict: Serialized estimate
    """
    if "_id" in estimate_doc:
        estimate_doc["_id"] = str(estimate_doc["_id"])
    
    # Convert datetime objects to ISO strings
    if "created_at" in estimate_doc:
        if isinstance(estimate_doc["created_at"], datetime):
            estimate_doc["created_at"] = estimate_doc["created_at"].isoformat()
    
    return estimate_doc


@router.get("/estimate/{estimate_id}", response_model=None)
async def get_estimate(estimate_id: str) -> JSONResponse:
    """
    Retrieve a complete estimate by ID.
    
    Returns the full estimate including all items, materials,
    audit trails, and verification results.
    
    Args:
        estimate_id: Unique estimate identifier
        
    Returns:
        JSONResponse: Complete estimate data
        
    Raises:
        HTTPException: 404 if estimate not found, 503 if database unavailable
    """
    logger.info(f"Fetching estimate: {estimate_id}")
    
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        collection = db["estimates"]
        
        # Find estimate by estimate_id
        estimate_doc = collection.find_one({"estimate_id": estimate_id})
        
        if not estimate_doc:
            logger.warning(f"Estimate not found: {estimate_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Estimate not found: {estimate_id}"
            )
        
        # Serialize for JSON response
        estimate_data = serialize_estimate(estimate_doc)
        
        logger.info(f"Estimate retrieved: {estimate_id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "estimate": estimate_data
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching estimate {estimate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch estimate: {str(e)}"
        )


@router.get("/estimates", response_model=None)
async def list_estimates(
    limit: int = Query(default=20, ge=1, le=100, description="Number of estimates to return"),
    offset: int = Query(default=0, ge=0, description="Number of estimates to skip"),
    status_filter: Optional[str] = Query(default=None, description="Filter by status")
) -> JSONResponse:
    """
    List all estimates with pagination.
    
    Returns a paginated list of estimates sorted by creation date (newest first).
    
    Args:
        limit: Maximum number of estimates to return (1-100, default 20)
        offset: Number of estimates to skip (default 0)
        status_filter: Optional status filter (completed, processing, error)
        
    Returns:
        JSONResponse: List of estimates with total count
        
    Raises:
        HTTPException: 503 if database unavailable
    """
    logger.info(f"Listing estimates: limit={limit}, offset={offset}, status={status_filter}")
    
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        collection = db["estimates"]
        
        # Build query filter
        query_filter = {}
        if status_filter:
            query_filter["status"] = status_filter
        
        # Get total count
        total_count = collection.count_documents(query_filter)
        
        # Fetch estimates with pagination
        cursor = collection.find(query_filter).sort("created_at", -1).skip(offset).limit(limit)
        estimates = list(cursor)
        
        # Serialize all estimates
        serialized_estimates = [serialize_estimate(est) for est in estimates]
        
        logger.info(f"Retrieved {len(serialized_estimates)} estimates (total: {total_count})")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "estimates": serialized_estimates,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(serialized_estimates)) < total_count
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing estimates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list estimates: {str(e)}"
        )


@router.delete("/estimate/{estimate_id}", response_model=None)
async def delete_estimate(estimate_id: str) -> JSONResponse:
    """
    Delete an estimate from the database.
    
    Permanently removes the estimate and all associated data.
    
    Args:
        estimate_id: Unique estimate identifier
        
    Returns:
        JSONResponse: Deletion confirmation
        
    Raises:
        HTTPException: 404 if estimate not found, 503 if database unavailable
    """
    logger.info(f"Deleting estimate: {estimate_id}")
    
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        collection = db["estimates"]
        
        # Check if estimate exists
        existing = collection.find_one({"estimate_id": estimate_id})
        if not existing:
            logger.warning(f"Estimate not found for deletion: {estimate_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Estimate not found: {estimate_id}"
            )
        
        # Delete estimate
        result = collection.delete_one({"estimate_id": estimate_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete estimate"
            )
        
        logger.info(f"Estimate deleted: {estimate_id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "deleted": True,
                "estimate_id": estimate_id,
                "message": f"Estimate {estimate_id} deleted successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting estimate {estimate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete estimate: {str(e)}"
        )


def generate_csv_export(estimate_doc: Dict[str, Any]) -> str:
    """
    Generate CSV export of estimate.
    
    Args:
        estimate_doc: Estimate document from MongoDB
        
    Returns:
        str: CSV content
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Estimate ID",
        "Filename",
        "Created At",
        "Intervention Type",
        "Quantity",
        "Unit",
        "Material",
        "Material Quantity",
        "Material Unit",
        "Unit Price (INR)",
        "Total Cost (INR)",
        "IRC Clause",
        "Price Source"
    ])
    
    # Write data rows
    estimate_id = estimate_doc.get("estimate_id", "N/A")
    filename = estimate_doc.get("filename", "N/A")
    created_at = estimate_doc.get("created_at", "N/A")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    items = estimate_doc.get("items", [])
    
    for item in items:
        intervention = item.get("intervention", {})
        intervention_type = intervention.get("type", "N/A")
        intervention_qty = intervention.get("quantity", 0)
        intervention_unit = intervention.get("unit", "N/A")
        
        materials = item.get("materials", [])
        
        if materials:
            for material in materials:
                writer.writerow([
                    estimate_id,
                    filename,
                    created_at,
                    intervention_type,
                    intervention_qty,
                    intervention_unit,
                    material.get("name", "N/A"),
                    material.get("quantity", 0),
                    material.get("unit", "N/A"),
                    material.get("unit_price", 0),
                    material.get("total_cost", 0),
                    material.get("irc_clause", "N/A"),
                    material.get("price_source", "N/A")
                ])
        else:
            # No materials - write intervention only
            writer.writerow([
                estimate_id,
                filename,
                created_at,
                intervention_type,
                intervention_qty,
                intervention_unit,
                "N/A",
                0,
                "N/A",
                0,
                0,
                "N/A",
                "N/A"
            ])
    
    # Write summary row
    writer.writerow([])
    writer.writerow([
        "TOTAL",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        estimate_doc.get("total_cost", 0),
        "",
        ""
    ])
    
    return output.getvalue()


def generate_json_export(estimate_doc: Dict[str, Any]) -> str:
    """
    Generate JSON export of estimate with complete audit trail.
    
    Args:
        estimate_doc: Estimate document from MongoDB
        
    Returns:
        str: Pretty-printed JSON
    """
    # Serialize for JSON
    export_data = serialize_estimate(estimate_doc.copy())
    
    # Add export metadata
    export_data["export_metadata"] = {
        "exported_at": datetime.now().isoformat(),
        "format": "json",
        "version": "1.0.0"
    }
    
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def generate_pdf_export(estimate_doc: Dict[str, Any]) -> str:
    """
    Generate PDF export of estimate with formatted report.
    
    Note: This is a simplified text-based implementation.
    For production, use reportlab or weasyprint for proper PDF generation.
    
    Args:
        estimate_doc: Estimate document from MongoDB
        
    Returns:
        str: Formatted text report (placeholder for actual PDF)
    """
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("BRAKES ROAD INTERVENTION COST ESTIMATE REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Estimate details
    lines.append(f"Estimate ID: {estimate_doc.get('estimate_id', 'N/A')}")
    lines.append(f"Filename: {estimate_doc.get('filename', 'N/A')}")
    
    created_at = estimate_doc.get("created_at", "N/A")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"Created At: {created_at}")
    
    lines.append(f"Status: {estimate_doc.get('status', 'N/A')}")
    lines.append(f"Overall Confidence: {estimate_doc.get('confidence', 0):.2%}")
    lines.append("")
    
    # Summary
    lines.append("-" * 80)
    lines.append("SUMMARY")
    lines.append("-" * 80)
    
    items = estimate_doc.get("items", [])
    lines.append(f"Total Interventions: {len(items)}")
    lines.append(f"Total Cost: INR {estimate_doc.get('total_cost', 0):,.2f}")
    lines.append("")
    
    # Items breakdown
    lines.append("-" * 80)
    lines.append("DETAILED BREAKDOWN")
    lines.append("-" * 80)
    lines.append("")
    
    for idx, item in enumerate(items, 1):
        intervention = item.get("intervention", {})
        
        lines.append(f"{idx}. {intervention.get('type', 'N/A').upper()}")
        lines.append(f"   Quantity: {intervention.get('quantity', 0)} {intervention.get('unit', 'N/A')}")
        lines.append(f"   Location: {intervention.get('location', 'N/A')}")
        lines.append(f"   Confidence: {intervention.get('confidence', 0):.2%}")
        lines.append("")
        
        # Materials
        materials = item.get("materials", [])
        if materials:
            lines.append("   Materials:")
            for material in materials:
                lines.append(f"     - {material.get('name', 'N/A')}")
                lines.append(f"       Quantity: {material.get('quantity', 0)} {material.get('unit', 'N/A')}")
                lines.append(f"       Unit Price: INR {material.get('unit_price', 0):,.2f}")
                lines.append(f"       Total: INR {material.get('total_cost', 0):,.2f}")
                lines.append(f"       IRC Clause: {material.get('irc_clause', 'N/A')}")
                lines.append(f"       Source: {material.get('price_source', 'N/A')}")
                lines.append("")
        
        lines.append(f"   Item Total Cost: INR {item.get('total_cost', 0):,.2f}")
        lines.append("")
        lines.append("   " + "-" * 76)
        lines.append("")
    
    # Footer
    lines.append("=" * 80)
    lines.append("CITATIONS AND REFERENCES")
    lines.append("=" * 80)
    lines.append("")
    lines.append("This estimate is based on:")
    lines.append("- Indian Roads Congress (IRC) specifications")
    lines.append("- CPWD Schedule of Rates (SOR) 2023/2024")
    lines.append("- GeM (Government e-Marketplace) pricing where applicable")
    lines.append("")
    lines.append("Note: This is an automated estimate. Please verify with current market rates")
    lines.append("and site conditions before finalizing procurement.")
    lines.append("")
    lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    
    return "\n".join(lines)


@router.get("/estimate/{estimate_id}/export", response_model=None)
async def export_estimate(
    estimate_id: str,
    format: str = Query(default="json", regex="^(csv|json|pdf)$", description="Export format")
) -> StreamingResponse:
    """
    Export estimate in various formats.
    
    Supports CSV, JSON, and PDF (text-based) export formats.
    
    Args:
        estimate_id: Unique estimate identifier
        format: Export format (csv, json, or pdf)
        
    Returns:
        StreamingResponse: File download
        
    Raises:
        HTTPException: 404 if estimate not found, 400 for invalid format
    """
    logger.info(f"Exporting estimate {estimate_id} as {format}")
    
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
            logger.warning(f"Estimate not found for export: {estimate_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Estimate not found: {estimate_id}"
            )
        
        # Generate export based on format
        if format == "csv":
            content = generate_csv_export(estimate_doc)
            media_type = "text/csv"
            filename = f"estimate_{estimate_id}.csv"
            
        elif format == "json":
            content = generate_json_export(estimate_doc)
            media_type = "application/json"
            filename = f"estimate_{estimate_id}.json"
            
        elif format == "pdf":
            content = generate_pdf_export(estimate_doc)
            media_type = "text/plain"  # Should be application/pdf for real PDF
            filename = f"estimate_{estimate_id}.txt"  # Should be .pdf for real PDF
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid export format: {format}. Must be csv, json, or pdf"
            )
        
        logger.info(f"Export generated: {estimate_id} as {format}")
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting estimate {estimate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export estimate: {str(e)}"
        )


@router.get("/estimate/{estimate_id}/summary", response_model=None)
async def get_estimate_summary(estimate_id: str) -> JSONResponse:
    """
    Get a brief summary of an estimate without full details.
    
    Useful for quick previews or dashboard displays.
    
    Args:
        estimate_id: Unique estimate identifier
        
    Returns:
        JSONResponse: Estimate summary
        
    Raises:
        HTTPException: 404 if estimate not found
    """
    logger.info(f"Fetching estimate summary: {estimate_id}")
    
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        collection = db["estimates"]
        
        # Find estimate with projection (only needed fields)
        estimate_doc = collection.find_one(
            {"estimate_id": estimate_id},
            {
                "estimate_id": 1,
                "filename": 1,
                "created_at": 1,
                "status": 1,
                "total_cost": 1,
                "confidence": 1,
                "items": 1,
                "metadata": 1
            }
        )
        
        if not estimate_doc:
            logger.warning(f"Estimate not found: {estimate_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Estimate not found: {estimate_id}"
            )
        
        # Build summary
        items = estimate_doc.get("items", [])
        items_summary = []
        
        for item in items:
            intervention = item.get("intervention", {})
            items_summary.append({
                "type": intervention.get("type"),
                "quantity": intervention.get("quantity"),
                "unit": intervention.get("unit"),
                "cost": item.get("total_cost", 0)
            })
        
        summary = {
            "success": True,
            "estimate_id": estimate_doc.get("estimate_id"),
            "filename": estimate_doc.get("filename"),
            "created_at": estimate_doc.get("created_at"),
            "status": estimate_doc.get("status"),
            "total_cost": estimate_doc.get("total_cost"),
            "confidence": estimate_doc.get("confidence"),
            "items_count": len(items),
            "items_summary": items_summary,
            "requires_review": estimate_doc.get("metadata", {}).get("requires_manual_review", False)
        }
        
        # Serialize dates
        if isinstance(summary["created_at"], datetime):
            summary["created_at"] = summary["created_at"].isoformat()
        
        logger.info(f"Estimate summary retrieved: {estimate_id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching estimate summary {estimate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch estimate summary: {str(e)}"
        )
