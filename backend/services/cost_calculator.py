"""
Cost Calculation Service

This module provides comprehensive cost calculation for road safety interventions,
integrating IRC clauses, quantity calculations, and price fetching.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from models.intervention import Intervention, Material, EstimateItem, Estimate
from services.clause_retriever import get_clause_by_intervention
from services.quantity_calculator import calculate_quantity
from services.price_fetcher import get_material_price, merge_prices, fetch_live_cpwd_price

# Configure logging
logger = logging.getLogger(__name__)


def calculate_cost(intervention: Intervention) -> EstimateItem:
    """
    Calculate complete cost estimate for a single intervention.
    
    This function orchestrates the entire calculation pipeline:
    1. Retrieve IRC clause specification
    2. Calculate material quantities
    3. Fetch current material prices
    4. Compute total cost
    5. Build comprehensive audit trail
    6. Compile assumptions
    
    Args:
        intervention: Intervention object with type, quantity, and metadata
        
    Returns:
        EstimateItem: Complete estimate with materials, costs, and audit trail
        
    Example:
        >>> from models.intervention import Intervention
        >>> intervention = Intervention(
        ...     type="speed_breaker",
        ...     quantity=10,
        ...     unit="units",
        ...     location="km 5-10",
        ...     confidence=0.95,
        ...     extraction_method="gemini"
        ... )
        >>> estimate_item = calculate_cost(intervention)
        >>> print(f"Total cost: ₹{estimate_item.total_cost}")
    """
    logger.info(
        f"Calculating cost for {intervention.type}: "
        f"{intervention.quantity} {intervention.unit}"
    )
    
    start_time = time.time()
    
    # Initialize tracking variables
    materials = []
    total_cost = 0.0
    audit_trail = {}
    assumptions = []
    warnings = []
    checks_passed = []
    
    # Step 1: Get IRC clause for intervention type
    logger.debug(f"Step 1: Retrieving IRC clause for {intervention.type}")
    irc_clause = get_clause_by_intervention(intervention.type)
    
    if irc_clause:
        audit_trail["clause_matching"] = {
            "standard": irc_clause.get("standard"),
            "clause": irc_clause.get("clause"),
            "title": irc_clause.get("title"),
            "page": irc_clause.get("page"),
            "category": irc_clause.get("category"),
            "matched": True
        }
        checks_passed.append("IRC clause found")
        logger.info(
            f"Found IRC clause: {irc_clause['standard']} {irc_clause['clause']}"
        )
    else:
        audit_trail["clause_matching"] = {
            "standard": None,
            "clause": None,
            "title": "Unrecognized intervention type",
            "matched": False,
            "requires_manual_review": True
        }
        warnings.append(
            f"No IRC clause found for intervention type '{intervention.type}'. "
            f"Manual review required."
        )
        logger.warning(
            f"No IRC clause found for {intervention.type}. "
            f"Marking for manual review."
        )
    
    # Step 2: Calculate material quantities
    logger.debug(f"Step 2: Calculating material quantities")
    quantity_result = calculate_quantity(
        intervention.type,
        intervention.quantity,
        irc_clause
    )
    
    if "error" in quantity_result:
        # Calculation error - log and create estimate item with error
        error_msg = quantity_result["error"]
        logger.error(f"Quantity calculation failed: {error_msg}")
        
        audit_trail["quantity_calculation"] = {
            "error": error_msg,
            "formula": None,
            "calculation": None,
            "result": 0
        }
        
        audit_trail["extraction"] = {
            "method": intervention.extraction_method,
            "confidence": intervention.confidence,
            "type": intervention.type,
            "quantity": intervention.quantity,
            "unit": intervention.unit
        }
        
        return EstimateItem(
            intervention=intervention,
            materials=[],
            total_cost=0.0,
            audit_trail=audit_trail,
            assumptions=["Calculation failed - manual review required"]
        )
    
    # Record quantity calculation
    audit_trail["quantity_calculation"] = {
        "formula": quantity_result.get("formula"),
        "calculation": quantity_result.get("calculation"),
        "result": quantity_result.get("quantity"),
        "unit": quantity_result.get("unit"),
        "irc_reference": quantity_result.get("irc_reference")
    }
    checks_passed.append("Quantity calculated successfully")
    
    # Add assumptions from quantity calculation
    if quantity_result.get("assumptions"):
        assumptions.extend(quantity_result["assumptions"])
    
    logger.info(
        f"Calculated {quantity_result['quantity']} {quantity_result['unit']} "
        f"of {quantity_result['material']}"
    )
    
    # Step 3: Fetch material price
    logger.debug(f"Step 3: Fetching material price")
    material_name = quantity_result["material"]
    price_info = get_material_price(material_name)
    
    if not price_info:
        # Price not found - use average as fallback
        logger.warning(
            f"Price not found for '{material_name}'. "
            f"Using fallback average price."
        )
        
        # TODO: Implement intelligent average calculation
        fallback_price = 5000  # Default fallback
        price_info = {
            "material": material_name,
            "unit": quantity_result["unit"],
            "price_inr": fallback_price,
            "source": "Fallback Average",
            "item_code": "N/A",
            "category": "Unknown",
            "fetched_date": datetime.now().strftime('%Y-%m-%d'),
            "confidence": 0.50,
            "description": "Fallback price - manual verification required"
        }
        warnings.append(
            f"Price for '{material_name}' not found in database. "
            f"Using fallback price of ₹{fallback_price}. "
            f"Manual verification recommended."
        )
        audit_trail["pricing"] = {
            "source": "Fallback",
            "unit_price": fallback_price,
            "fetched_date": price_info["fetched_date"],
            "confidence": 0.50,
            "warning": "Price not in database"
        }
    else:
        # Price found
        checks_passed.append("Material price found")
        
        # Check if fuzzy match was used
        if price_info.get("fuzzy_match"):
            warnings.append(
                f"Fuzzy match used: '{material_name}' → "
                f"'{price_info['matched_to']}'"
            )
        
        audit_trail["pricing"] = {
            "source": price_info.get("source"),
            "unit_price": price_info.get("price_inr"),
            "fetched_date": price_info.get("fetched_date"),
            "confidence": price_info.get("confidence"),
            "item_code": price_info.get("item_code"),
            "fuzzy_match": price_info.get("fuzzy_match", False)
        }
        
        logger.info(
            f"Found price: ₹{price_info['price_inr']}/{price_info['unit']} "
            f"from {price_info['source']}"
        )
    
    # Add pricing assumption
    assumptions.append(f"Pricing from {price_info['source']}")
    
    # Step 4: Calculate total cost
    logger.debug(f"Step 4: Calculating total cost")
    material_quantity = quantity_result["quantity"]
    unit_price = price_info["price_inr"]
    material_cost = round(material_quantity * unit_price, 2)
    
    logger.info(
        f"Cost calculation: {material_quantity} × ₹{unit_price} = ₹{material_cost}"
    )
    
    # Create Material object
    material = Material(
        name=material_name,
        quantity=material_quantity,
        unit=quantity_result["unit"],
        unit_price=unit_price,
        total_cost=material_cost,
        irc_clause=irc_clause["standard"] + ":" + irc_clause["clause"] if irc_clause else "N/A",
        price_source=price_info["source"],
        fetched_date=datetime.now()
    )
    
    materials.append(material)
    total_cost = material_cost
    
    # Step 5: Record extraction information in audit trail
    audit_trail["extraction"] = {
        "method": intervention.extraction_method,
        "confidence": intervention.confidence,
        "type": intervention.type,
        "quantity": intervention.quantity,
        "unit": intervention.unit,
        "location": intervention.location
    }
    
    # Step 6: Verification summary
    processing_time = round(time.time() - start_time, 3)
    
    audit_trail["verification"] = {
        "checks_passed": checks_passed,
        "warnings": warnings,
        "total_checks": len(checks_passed),
        "total_warnings": len(warnings),
        "processing_time_seconds": processing_time,
        "timestamp": datetime.now().isoformat()
    }
    
    # Add standard assumptions
    if irc_clause:
        assumptions.append(f"IRC {irc_clause['standard']} specifications used")
    assumptions.append("Standard material specifications assumed")
    assumptions.append("CPWD SOR 2023/2024 pricing basis")
    
    # Create EstimateItem
    estimate_item = EstimateItem(
        intervention=intervention,
        materials=materials,
        total_cost=total_cost,
        audit_trail=audit_trail,
        assumptions=assumptions
    )
    
    logger.info(
        f"Cost calculation complete for {intervention.type}: "
        f"₹{total_cost} ({processing_time}s)"
    )
    
    return estimate_item


def calculate_total_estimate(
    interventions: List[Intervention],
    estimate_id: Optional[str] = None,
    filename: Optional[str] = None
) -> Estimate:
    """
    Calculate complete cost estimate for multiple interventions.
    
    Processes each intervention, computes individual and total costs,
    and generates a comprehensive Estimate object with metadata.
    
    Args:
        interventions: List of Intervention objects to estimate
        estimate_id: Optional custom estimate ID (generated if not provided)
        filename: Optional source filename
        
    Returns:
        Estimate: Complete estimate with all items, costs, and metadata
        
    Example:
        >>> interventions = [intervention1, intervention2, intervention3]
        >>> estimate = calculate_total_estimate(interventions, filename="audit.pdf")
        >>> print(f"Total: ₹{estimate.total_cost} for {len(estimate.items)} items")
    """
    start_time = time.time()
    
    logger.info(f"Calculating total estimate for {len(interventions)} interventions")
    
    # Generate estimate ID if not provided
    if not estimate_id:
        estimate_id = f"EST-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Initialize tracking
    estimate_items = []
    total_cost = 0.0
    confidence_scores = []
    errors_count = 0
    warnings_count = 0
    
    # Process each intervention
    for i, intervention in enumerate(interventions, 1):
        logger.info(f"Processing intervention {i}/{len(interventions)}: {intervention.type}")
        
        try:
            estimate_item = calculate_cost(intervention)
            estimate_items.append(estimate_item)
            total_cost += estimate_item.total_cost
            confidence_scores.append(intervention.confidence)
            
            # Count warnings
            verification = estimate_item.audit_trail.get("verification", {})
            warnings_count += len(verification.get("warnings", []))
            
        except Exception as e:
            logger.error(
                f"Failed to calculate cost for intervention {i} "
                f"({intervention.type}): {str(e)}"
            )
            errors_count += 1
            
            # Create error estimate item
            error_item = EstimateItem(
                intervention=intervention,
                materials=[],
                total_cost=0.0,
                audit_trail={
                    "error": str(e),
                    "extraction": {
                        "method": intervention.extraction_method,
                        "confidence": intervention.confidence,
                        "type": intervention.type
                    }
                },
                assumptions=["Calculation failed - manual review required"]
            )
            estimate_items.append(error_item)
    
    # Calculate overall confidence (average of all interventions)
    if confidence_scores:
        overall_confidence = round(sum(confidence_scores) / len(confidence_scores), 2)
    else:
        overall_confidence = 0.0
    
    # Calculate processing time
    processing_time = round(time.time() - start_time, 2)
    
    # Build metadata
    metadata = {
        "processing_time_seconds": processing_time,
        "interventions_processed": len(interventions),
        "items_with_costs": len([item for item in estimate_items if item.total_cost > 0]),
        "total_warnings": warnings_count,
        "total_errors": errors_count,
        "processor_version": "1.0.0",
        "calculation_method": "IRC-based deterministic",
        "timestamp": datetime.now().isoformat()
    }
    
    # Add manual review flag if there are errors or warnings
    if errors_count > 0 or warnings_count > 0:
        metadata["requires_manual_review"] = True
        metadata["review_reason"] = []
        
        if errors_count > 0:
            metadata["review_reason"].append(f"{errors_count} calculation errors")
        if warnings_count > 0:
            metadata["review_reason"].append(f"{warnings_count} warnings")
    
    # Create Estimate object
    estimate = Estimate(
        estimate_id=estimate_id,
        filename=filename or "unknown",
        created_at=datetime.now(),
        status="completed" if errors_count == 0 else "completed_with_errors",
        items=estimate_items,
        total_cost=round(total_cost, 2),
        confidence=overall_confidence,
        metadata=metadata
    )
    
    logger.info(
        f"Total estimate calculated: ₹{total_cost} for {len(estimate_items)} items "
        f"(confidence: {overall_confidence}, time: {processing_time}s)"
    )
    
    if errors_count > 0:
        logger.warning(f"Estimate completed with {errors_count} errors")
    
    return estimate


def recalculate_with_adjustments(
    estimate: Estimate,
    price_adjustments: Optional[Dict[str, float]] = None,
    quantity_adjustments: Optional[Dict[str, float]] = None
) -> Estimate:
    """
    Recalculate an estimate with price or quantity adjustments.
    
    Useful for scenarios like:
    - Applying location-based price variations
    - Adjusting for bulk discounts
    - Modifying quantities based on field verification
    
    Args:
        estimate: Original Estimate object
        price_adjustments: Dict of material_name -> adjustment_factor (1.1 = +10%)
        quantity_adjustments: Dict of intervention_type -> adjustment_factor
        
    Returns:
        Estimate: New estimate with adjustments applied
    """
    logger.info(f"Recalculating estimate {estimate.estimate_id} with adjustments")
    
    # Extract interventions from estimate items
    interventions = [item.intervention for item in estimate.items]
    
    # Apply quantity adjustments if provided
    if quantity_adjustments:
        for intervention in interventions:
            if intervention.type in quantity_adjustments:
                factor = quantity_adjustments[intervention.type]
                original = intervention.quantity
                intervention.quantity = round(original * factor, 2)
                logger.info(
                    f"Adjusted {intervention.type} quantity: "
                    f"{original} → {intervention.quantity} (×{factor})"
                )
    
    # Recalculate
    # Note: Price adjustments would need to be applied during calculate_cost
    # For now, we'll recalculate with current prices
    new_estimate = calculate_total_estimate(
        interventions,
        estimate_id=estimate.estimate_id + "-ADJ",
        filename=estimate.filename
    )
    
    # Add adjustment metadata
    new_estimate.metadata["adjusted_from"] = estimate.estimate_id
    new_estimate.metadata["adjustments_applied"] = True
    
    if price_adjustments:
        new_estimate.metadata["price_adjustments"] = price_adjustments
    if quantity_adjustments:
        new_estimate.metadata["quantity_adjustments"] = quantity_adjustments
    
    return new_estimate


def get_estimate_summary(estimate: Estimate) -> Dict[str, Any]:
    """
    Generate a human-readable summary of an estimate.
    
    Args:
        estimate: Estimate object
        
    Returns:
        Dict: Summary with key metrics and breakdowns
    """
    summary = {
        "estimate_id": estimate.estimate_id,
        "total_cost": estimate.total_cost,
        "total_items": len(estimate.items),
        "confidence": estimate.confidence,
        "status": estimate.status,
        "created_at": estimate.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        "items_breakdown": []
    }
    
    # Add breakdown by intervention type
    for item in estimate.items:
        summary["items_breakdown"].append({
            "type": item.intervention.type,
            "quantity": item.intervention.quantity,
            "unit": item.intervention.unit,
            "cost": item.total_cost,
            "confidence": item.intervention.confidence
        })
    
    # Add warnings if any
    if estimate.metadata.get("requires_manual_review"):
        summary["requires_review"] = True
        summary["review_reasons"] = estimate.metadata.get("review_reason", [])
    
    return summary
