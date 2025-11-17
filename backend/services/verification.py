"""
Cost Verification Service

This module provides sanity checks and validation for cost calculations,
ensuring accuracy and consistency of estimates.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from models.intervention import EstimateItem, Estimate, Material

# Configure logging
logger = logging.getLogger(__name__)

# Price range expectations (in INR) for different material categories
PRICE_RANGES = {
    "concrete": {
        "min": 4000,
        "max": 8000,
        "unit": "cum",
        "description": "Concrete (all grades)"
    },
    "steel": {
        "min": 50,
        "max": 100,
        "unit": "kg",
        "description": "Steel materials"
    },
    "paint": {
        "min": 150,
        "max": 400,
        "unit": "kg",
        "description": "Paints and marking materials"
    },
    "thermoplastic": {
        "min": 150,
        "max": 250,
        "unit": "kg",
        "description": "Thermoplastic road marking"
    },
    "reflective": {
        "min": 800,
        "max": 1500,
        "unit": "sqm",
        "description": "Reflective sheeting"
    },
    "lights": {
        "min": 4000,
        "max": 10000,
        "unit": "nos",
        "description": "LED luminaires"
    },
    "signs": {
        "min": 1500,
        "max": 4500,
        "unit": "nos",
        "description": "Traffic signs"
    },
    "pole": {
        "min": 10000,
        "max": 15000,
        "unit": "nos",
        "description": "Lighting/sign poles"
    },
    "barrier": {
        "min": 500,
        "max": 2000,
        "unit": "meter",
        "description": "Barriers and bollards"
    },
    "aggregates": {
        "min": 1000,
        "max": 2000,
        "unit": "cum",
        "description": "Sand, gravel, aggregates"
    }
}

# Unit conversion factors
UNIT_CONVERSIONS = {
    "cum": ["m3", "cubic meter", "cubic metre"],
    "sqm": ["m2", "square meter", "square metre"],
    "kg": ["kilogram", "kgs"],
    "meter": ["m", "metre", "meters"],
    "nos": ["unit", "units", "number", "no"],
    "liter": ["litre", "l"],
    "quintal": ["qtl"]
}


def _normalize_unit(unit: str) -> str:
    """
    Normalize unit to standard form.
    
    Args:
        unit: Unit string to normalize
        
    Returns:
        str: Normalized unit
    """
    unit_lower = unit.lower().strip()
    
    for standard_unit, aliases in UNIT_CONVERSIONS.items():
        if unit_lower == standard_unit or unit_lower in aliases:
            return standard_unit
    
    return unit_lower


def _detect_material_category(material_name: str) -> Optional[str]:
    """
    Detect material category from material name.
    
    Args:
        material_name: Name of the material
        
    Returns:
        str: Category key or None
    """
    material_lower = material_name.lower()
    
    # Check for concrete
    if "concrete" in material_lower or "cement" in material_lower:
        return "concrete"
    
    # Check for steel
    if any(word in material_lower for word in ["steel", "tmt", "bar", "beam", "pipe", "ms", "gi"]):
        return "steel"
    
    # Check for paint/marking
    if "thermoplastic" in material_lower:
        return "thermoplastic"
    if any(word in material_lower for word in ["paint", "enamel", "acrylic", "marking"]):
        return "paint"
    
    # Check for reflective materials
    if "reflective" in material_lower or "sheeting" in material_lower:
        return "reflective"
    
    # Check for lights
    if "led" in material_lower or "luminaire" in material_lower or "light" in material_lower:
        return "lights"
    
    # Check for signs
    if "sign" in material_lower or "board" in material_lower:
        return "signs"
    
    # Check for poles
    if "pole" in material_lower or "post" in material_lower:
        return "pole"
    
    # Check for barriers
    if any(word in material_lower for word in ["barrier", "guardrail", "bollard", "fence"]):
        return "barrier"
    
    # Check for aggregates
    if any(word in material_lower for word in ["sand", "aggregate", "gravel", "stone", "brick"]):
        return "aggregates"
    
    return None


def _check_price_reasonability(
    material_name: str,
    unit_price: float,
    unit: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if price is within reasonable range for the material type.
    
    Args:
        material_name: Name of the material
        unit_price: Price per unit
        unit: Unit of measurement
        
    Returns:
        Tuple of (is_reasonable, warning_message)
    """
    category = _detect_material_category(material_name)
    
    if not category:
        # Can't verify without category
        logger.debug(f"Cannot determine category for material: {material_name}")
        return True, None
    
    expected_range = PRICE_RANGES.get(category)
    if not expected_range:
        return True, None
    
    # Normalize units for comparison
    normalized_unit = _normalize_unit(unit)
    expected_unit = _normalize_unit(expected_range["unit"])
    
    if normalized_unit != expected_unit:
        # Units don't match, can't compare
        return True, f"Unit mismatch: expected {expected_range['unit']}, got {unit}"
    
    # Check if price is within range
    min_price = expected_range["min"]
    max_price = expected_range["max"]
    
    if unit_price < min_price:
        warning = (
            f"Price unusually low: ₹{unit_price}/{unit} "
            f"(expected range: ₹{min_price}-{max_price}/{unit} for {expected_range['description']})"
        )
        logger.warning(warning)
        return False, warning
    
    if unit_price > max_price:
        warning = (
            f"Price unusually high: ₹{unit_price}/{unit} "
            f"(expected range: ₹{min_price}-{max_price}/{unit} for {expected_range['description']})"
        )
        logger.warning(warning)
        return False, warning
    
    logger.debug(f"Price reasonable for {material_name}: ₹{unit_price}/{unit}")
    return True, None


def _check_math_accuracy(material: Material) -> Tuple[bool, Optional[str]]:
    """
    Verify that quantity × unit_price == total_cost.
    
    Args:
        material: Material object to check
        
    Returns:
        Tuple of (is_correct, error_message)
    """
    expected_total = round(material.quantity * material.unit_price, 2)
    actual_total = round(material.total_cost, 2)
    
    # Allow small floating point differences (0.01)
    if abs(expected_total - actual_total) > 0.01:
        error = (
            f"Math error: {material.quantity} × ₹{material.unit_price} "
            f"= ₹{expected_total}, but total_cost is ₹{actual_total}"
        )
        logger.error(error)
        return False, error
    
    return True, None


def _check_units_consistency(material: Material) -> Tuple[bool, Optional[str]]:
    """
    Check if units are consistent and valid.
    
    Args:
        material: Material object to check
        
    Returns:
        Tuple of (is_valid, warning_message)
    """
    # Check if unit is recognized
    normalized_unit = _normalize_unit(material.unit)
    
    if normalized_unit not in UNIT_CONVERSIONS and material.unit.lower() not in [
        "cum", "sqm", "kg", "meter", "nos", "liter", "quintal", "tonne", "thousand"
    ]:
        warning = f"Unrecognized unit: {material.unit}"
        logger.warning(warning)
        return False, warning
    
    return True, None


def verify_cost_item(item: EstimateItem) -> Dict:
    """
    Perform comprehensive verification checks on a cost estimate item.
    
    Verifies:
    - Mathematical accuracy (quantity × price = total)
    - Unit consistency
    - Price reasonability against expected ranges
    - IRC clause validity
    - Material existence in database
    
    Args:
        item: EstimateItem to verify
        
    Returns:
        Dict containing:
            - passed: Overall pass/fail status
            - status: Human-readable status ("✅ VERIFIED", "⚠️ NEEDS REVIEW", "❌ FAILED")
            - checks: Dictionary of individual check results
            - warnings: List of warning messages
            - errors: List of error messages
    """
    logger.info(
        f"Verifying cost item: {item.intervention.type} "
        f"({item.intervention.quantity} {item.intervention.unit})"
    )
    
    checks = {
        "math_correct": True,
        "units_valid": True,
        "price_reasonable": True,
        "clause_valid": True,
        "material_found": True
    }
    
    warnings = []
    errors = []
    
    # Check 1: Mathematical accuracy for each material
    if item.materials:
        for material in item.materials:
            is_correct, error_msg = _check_math_accuracy(material)
            if not is_correct:
                checks["math_correct"] = False
                errors.append(error_msg)
        
        # Also check total item cost
        materials_total = round(sum(m.total_cost for m in item.materials), 2)
        item_total = round(item.total_cost, 2)
        
        if abs(materials_total - item_total) > 0.01:
            checks["math_correct"] = False
            error = (
                f"Item total mismatch: sum of materials = ₹{materials_total}, "
                f"but item total = ₹{item_total}"
            )
            errors.append(error)
            logger.error(error)
    else:
        warnings.append("No materials listed for this item")
        checks["material_found"] = False
    
    # Check 2: Units consistency
    if item.materials:
        for material in item.materials:
            is_valid, warning_msg = _check_units_consistency(material)
            if not is_valid:
                checks["units_valid"] = False
                warnings.append(warning_msg)
    
    # Check 3: Price reasonability
    if item.materials:
        for material in item.materials:
            is_reasonable, warning_msg = _check_price_reasonability(
                material.name,
                material.unit_price,
                material.unit
            )
            if not is_reasonable:
                checks["price_reasonable"] = False
                if warning_msg:
                    warnings.append(warning_msg)
    
    # Check 4: IRC clause validity
    if item.materials:
        for material in item.materials:
            irc_clause = material.irc_clause
            if not irc_clause or irc_clause.strip() == "":
                checks["clause_valid"] = False
                warnings.append(f"Missing IRC clause for material: {material.name}")
            elif not irc_clause.startswith("IRC"):
                checks["clause_valid"] = False
                warnings.append(f"Invalid IRC clause format: {irc_clause}")
    else:
        checks["clause_valid"] = False
        warnings.append("No IRC clause information available")
    
    # Check 5: Material found in database
    if not item.materials:
        checks["material_found"] = False
        warnings.append("No materials found in database for this intervention")
    
    # Determine overall status
    all_passed = all(checks.values())
    has_errors = len(errors) > 0
    has_warnings = len(warnings) > 0
    
    if all_passed and not has_errors and not has_warnings:
        status = "✅ VERIFIED"
        passed = True
    elif has_errors:
        status = "❌ FAILED"
        passed = False
    else:
        status = "⚠️ NEEDS REVIEW"
        passed = True  # Warnings don't fail the item
    
    logger.info(
        f"Verification complete for {item.intervention.type}: {status} "
        f"(errors: {len(errors)}, warnings: {len(warnings)})"
    )
    
    return {
        "passed": passed,
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "intervention_type": item.intervention.type,
        "intervention_quantity": item.intervention.quantity,
        "total_cost": item.total_cost
    }


def verify_estimate(estimate: Estimate) -> Dict:
    """
    Verify all items in a complete estimate.
    
    Runs verification on each item and aggregates results
    into a summary report.
    
    Args:
        estimate: Complete estimate to verify
        
    Returns:
        Dict containing:
            - overall_status: Overall pass/fail status
            - total_items: Total number of items
            - passed_count: Number of items that passed
            - warning_count: Number of items with warnings
            - error_count: Number of items with errors
            - items_verification: List of individual item verification results
            - summary: Human-readable summary
            - recommendations: List of recommended actions
    """
    logger.info(f"Verifying estimate: {estimate.estimate_id}")
    
    if not estimate.items:
        logger.warning("Estimate has no items to verify")
        return {
            "overall_status": "❌ FAILED",
            "total_items": 0,
            "passed_count": 0,
            "warning_count": 0,
            "error_count": 0,
            "items_verification": [],
            "summary": "No items found in estimate",
            "recommendations": ["Add items to the estimate before verification"]
        }
    
    items_verification = []
    passed_count = 0
    warning_count = 0
    error_count = 0
    
    # Verify each item
    for i, item in enumerate(estimate.items, 1):
        logger.debug(f"Verifying item {i}/{len(estimate.items)}")
        
        verification_result = verify_cost_item(item)
        items_verification.append(verification_result)
        
        if verification_result["passed"]:
            if len(verification_result["warnings"]) > 0:
                warning_count += 1
            else:
                passed_count += 1
        else:
            error_count += 1
    
    # Determine overall status
    if error_count > 0:
        overall_status = "❌ FAILED"
    elif warning_count > 0:
        overall_status = "⚠️ NEEDS REVIEW"
    else:
        overall_status = "✅ VERIFIED"
    
    # Generate summary
    total_items = len(estimate.items)
    summary = (
        f"Verified {total_items} items: "
        f"{passed_count} passed, "
        f"{warning_count} with warnings, "
        f"{error_count} failed"
    )
    
    # Generate recommendations
    recommendations = []
    
    if error_count > 0:
        recommendations.append(
            f"Review and fix {error_count} items with errors before proceeding"
        )
    
    if warning_count > 0:
        recommendations.append(
            f"Review {warning_count} items with warnings for potential issues"
        )
    
    # Check for common issues across items
    all_warnings = []
    all_errors = []
    for result in items_verification:
        all_warnings.extend(result["warnings"])
        all_errors.extend(result["errors"])
    
    if any("IRC clause" in w for w in all_warnings):
        recommendations.append("Multiple items missing IRC clause references")
    
    if any("Price unusually" in w for w in all_warnings):
        recommendations.append("Some prices are outside expected ranges - verify with latest SOR")
    
    if any("Math error" in e for e in all_errors):
        recommendations.append("Critical: Mathematical calculation errors detected")
    
    if not recommendations:
        recommendations.append("All checks passed - estimate is ready for review")
    
    logger.info(
        f"Estimate verification complete: {overall_status} - {summary}"
    )
    
    return {
        "overall_status": overall_status,
        "total_items": total_items,
        "passed_count": passed_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "items_verification": items_verification,
        "summary": summary,
        "recommendations": recommendations,
        "verified_at": datetime.now().isoformat(),
        "estimate_id": estimate.estimate_id,
        "estimate_total": estimate.total_cost
    }


def get_verification_summary(verification_result: Dict) -> str:
    """
    Generate a human-readable summary of verification results.
    
    Args:
        verification_result: Result from verify_estimate()
        
    Returns:
        str: Formatted summary text
    """
    lines = [
        "=" * 60,
        f"ESTIMATE VERIFICATION REPORT",
        "=" * 60,
        f"Estimate ID: {verification_result.get('estimate_id', 'N/A')}",
        f"Verified At: {verification_result.get('verified_at', 'N/A')}",
        f"Overall Status: {verification_result.get('overall_status', 'N/A')}",
        "",
        f"Summary: {verification_result.get('summary', 'N/A')}",
        "",
        "Items Breakdown:",
        f"  ✅ Passed: {verification_result.get('passed_count', 0)}",
        f"  ⚠️  Warnings: {verification_result.get('warning_count', 0)}",
        f"  ❌ Errors: {verification_result.get('error_count', 0)}",
        "",
        "Recommendations:",
    ]
    
    for rec in verification_result.get('recommendations', []):
        lines.append(f"  • {rec}")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)
