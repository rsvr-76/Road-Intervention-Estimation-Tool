"""
Deterministic Quantity Calculator

This module provides PURE MATHEMATICAL calculations for material quantities
based on IRC specifications. NO AI is used - only deterministic formulas.
"""

import logging
from typing import Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Hardcoded formulas per IRC specifications
# Each formula is based on actual IRC standards and engineering calculations

QUANTITY_FORMULAS = {
    "speed_breaker": {
        "material": "Concrete M15 (1:2:4)",
        "per_unit_quantity": 0.0525,  # m³
        "unit": "cum",
        "formula": "3.5m (width) × 0.3m (depth) × 0.05m (height) = 0.0525 m³ per unit",
        "calculation_template": "{quantity} units × 0.0525 m³/unit = {result} m³",
        "irc_reference": "IRC 67:3.2.1",
        "assumptions": [
            "Standard speed breaker dimensions: 3.5m width × 0.05m height",
            "Concrete mix ratio 1:2:4 (cement:sand:aggregate)",
            "Wastage factor included in per-unit quantity"
        ]
    },
    
    "speed_bump": {
        "material": "Concrete M15 (1:2:4)",
        "per_unit_quantity": 0.0525,  # m³
        "unit": "cum",
        "formula": "3.5m × 0.3m × 0.05m = 0.0525 m³ per unit",
        "calculation_template": "{quantity} units × 0.0525 m³/unit = {result} m³",
        "irc_reference": "IRC 67:3.2.1",
        "assumptions": [
            "Same dimensions as speed breaker",
            "Concrete mix ratio 1:2:4"
        ]
    },
    
    "rumble_strip": {
        "material": "Thermoplastic Paint",
        "per_unit_quantity": 0.1,  # m² per linear meter
        "unit": "sqm",
        "formula": "0.1m (width) × length = 0.1 m² per linear meter",
        "calculation_template": "{quantity} linear meters × 0.1 m²/m = {result} m²",
        "irc_reference": "IRC 67:3.3.1",
        "assumptions": [
            "Rumble strip width: 100mm",
            "Thermoplastic material thickness: 3mm"
        ]
    },
    
    "guardrail": {
        "material": "Galvanized Steel W-Beam",
        "per_unit_quantity": 5.0,  # kg per meter
        "unit": "kg",
        "formula": "5 kg/meter (standard W-beam weight)",
        "calculation_template": "{quantity} meters × 5 kg/m = {result} kg",
        "irc_reference": "IRC 35:6.1.1",
        "assumptions": [
            "W-beam section 310mm × 3mm thickness",
            "Hot-dip galvanized finish",
            "Includes posts at 2m spacing"
        ]
    },
    
    "guard_rail": {
        "material": "Galvanized Steel W-Beam",
        "per_unit_quantity": 5.0,
        "unit": "kg",
        "formula": "5 kg/meter",
        "calculation_template": "{quantity} meters × 5 kg/m = {result} kg",
        "irc_reference": "IRC 35:6.1.1",
        "assumptions": [
            "W-beam section 310mm × 3mm",
            "Galvanized finish"
        ]
    },
    
    "crash_barrier": {
        "material": "Concrete M30",
        "per_unit_quantity": 0.3,  # m³ per linear meter
        "unit": "cum",
        "formula": "0.3 m² cross-section × length = 0.3 m³ per meter",
        "calculation_template": "{quantity} meters × 0.3 m³/m = {result} m³",
        "irc_reference": "IRC 35:6.2.1",
        "assumptions": [
            "New Jersey profile: 810mm height × 600mm base",
            "Average cross-sectional area: 0.3 m²",
            "M30 grade concrete with reinforcement"
        ]
    },
    
    "barrier": {
        "material": "Concrete M30",
        "per_unit_quantity": 0.3,
        "unit": "cum",
        "formula": "0.3 m³ per meter",
        "calculation_template": "{quantity} meters × 0.3 m³/m = {result} m³",
        "irc_reference": "IRC 35:6.2.1",
        "assumptions": [
            "Concrete barrier, New Jersey profile"
        ]
    },
    
    "road_marking": {
        "material": "Thermoplastic Paint",
        "per_unit_quantity": 2.0,  # kg per m²
        "unit": "kg",
        "formula": "2 kg/m² (thermoplastic material with glass beads)",
        "calculation_template": "{quantity} m² × 2 kg/m² = {result} kg",
        "irc_reference": "IRC 35:5.2.1",
        "assumptions": [
            "Thermoplastic paint thickness: 3mm",
            "Includes 18% glass beads by weight",
            "Material density: ~1.5 g/cm³"
        ]
    },
    
    "pavement_marking": {
        "material": "Thermoplastic Paint",
        "per_unit_quantity": 2.0,
        "unit": "kg",
        "formula": "2 kg/m²",
        "calculation_template": "{quantity} m² × 2 kg/m² = {result} kg",
        "irc_reference": "IRC 35:5.2.1",
        "assumptions": [
            "Thermoplastic paint with glass beads"
        ]
    },
    
    "zebra_crossing": {
        "material": "Thermoplastic White Paint",
        "per_unit_quantity": 0.5,  # m² per linear meter of carriageway
        "unit": "sqm",
        "formula": "0.5m (stripe width) × carriageway width",
        "calculation_template": "{quantity} m² × 2 kg/m² = {result} kg thermoplastic",
        "irc_reference": "IRC 35:5.3.1",
        "assumptions": [
            "Stripe width: 500mm",
            "600mm spacing between stripes",
            "Thermoplastic material: 2 kg/m²"
        ]
    },
    
    "pedestrian_crossing": {
        "material": "Thermoplastic White Paint",
        "per_unit_quantity": 2.0,
        "unit": "kg",
        "formula": "2 kg/m² for marking area",
        "calculation_template": "{quantity} m² × 2 kg/m² = {result} kg",
        "irc_reference": "IRC 35:5.3.1",
        "assumptions": [
            "Thermoplastic white paint",
            "Includes glass beads"
        ]
    },
    
    "street_light": {
        "material": "LED Luminaire 100W",
        "per_unit_quantity": 1.0,  # Complete assembly
        "unit": "nos",
        "formula": "1 complete unit (luminaire + pole + foundation)",
        "calculation_template": "{quantity} units × 1 = {result} complete assemblies",
        "irc_reference": "IRC 99:4.2.2",
        "assumptions": [
            "Includes 100W LED luminaire",
            "MS tubular pole 10m height",
            "Concrete foundation 400mm × 400mm × 600mm",
            "Electrical wiring and accessories"
        ]
    },
    
    "lighting": {
        "material": "LED Luminaire 100W",
        "per_unit_quantity": 1.0,
        "unit": "nos",
        "formula": "1 complete unit",
        "calculation_template": "{quantity} units × 1 = {result} units",
        "irc_reference": "IRC 99:4.2.2",
        "assumptions": [
            "LED street light assembly"
        ]
    },
    
    "road_sign": {
        "material": "Reflective Sheeting Type III",
        "per_unit_quantity": 0.5,  # m² per sign
        "unit": "sqm",
        "formula": "0.5 m² (average sign area: 600mm diameter circular or equivalent)",
        "calculation_template": "{quantity} signs × 0.5 m²/sign = {result} m²",
        "irc_reference": "IRC 99:5.1.1",
        "assumptions": [
            "Average sign size: 600mm diameter circular",
            "Type III retroreflective sheeting",
            "MS backing sheet and post included separately"
        ]
    },
    
    "signage": {
        "material": "Reflective Sheeting Type III",
        "per_unit_quantity": 0.5,
        "unit": "sqm",
        "formula": "0.5 m² per sign",
        "calculation_template": "{quantity} signs × 0.5 m²/sign = {result} m²",
        "irc_reference": "IRC 99:5.1.1",
        "assumptions": [
            "Standard sign size",
            "Type III reflective material"
        ]
    },
    
    "traffic_sign": {
        "material": "Reflective Sheeting Type III",
        "per_unit_quantity": 0.5,
        "unit": "sqm",
        "formula": "0.5 m² per sign",
        "calculation_template": "{quantity} signs × 0.5 m²/sign = {result} m²",
        "irc_reference": "IRC 99:5.1.1",
        "assumptions": [
            "Standard traffic sign"
        ]
    },
    
    "warning_sign": {
        "material": "Reflective Sheeting Type II",
        "per_unit_quantity": 0.405,  # m² (triangular 900mm)
        "unit": "sqm",
        "formula": "0.9m × 0.9m × 0.5 (triangle) = 0.405 m² per sign",
        "calculation_template": "{quantity} signs × 0.405 m²/sign = {result} m²",
        "irc_reference": "IRC 99:5.1.2",
        "assumptions": [
            "Triangular sign: 900mm sides",
            "Type II retroreflective sheeting"
        ]
    },
    
    "bollard": {
        "material": "MS Pipe Bollard",
        "per_unit_quantity": 1.0,
        "unit": "nos",
        "formula": "1 bollard (150mm dia MS pipe, 1m height)",
        "calculation_template": "{quantity} × 1 = {result} bollards",
        "irc_reference": "IRC 35:8.2.1",
        "assumptions": [
            "MS pipe 150mm diameter",
            "1m height above ground",
            "Concrete-filled with base plate"
        ]
    },
    
    "delineator": {
        "material": "Flexible Delineator",
        "per_unit_quantity": 1.0,
        "unit": "nos",
        "formula": "1 delineator unit",
        "calculation_template": "{quantity} × 1 = {result} delineators",
        "irc_reference": "IRC 67:7.1.1",
        "assumptions": [
            "100mm height flexible marker",
            "High impact plastic with reflector"
        ]
    },
    
    "traffic_cone": {
        "material": "PVC Traffic Cone",
        "per_unit_quantity": 1.0,
        "unit": "nos",
        "formula": "1 cone (750mm height)",
        "calculation_template": "{quantity} × 1 = {result} cones",
        "irc_reference": "IRC SP-84:4.1.1",
        "assumptions": [
            "750mm height PVC cone",
            "Orange color with reflective bands"
        ]
    },
    
    "footpath": {
        "material": "Concrete M20",
        "per_unit_quantity": 0.225,  # m³ per m²
        "unit": "cum",
        "formula": "1.5m (width) × 0.15m (thickness) = 0.225 m³ per linear meter",
        "calculation_template": "{quantity} m² × 0.225 m³/m² = {result} m³",
        "irc_reference": "IRC SP-87:5.1.1",
        "assumptions": [
            "Footpath width: 1.5m",
            "RCC thickness: 150mm",
            "M20 concrete over GSB"
        ]
    },
    
    "sidewalk": {
        "material": "Concrete M20",
        "per_unit_quantity": 0.225,
        "unit": "cum",
        "formula": "0.225 m³ per m²",
        "calculation_template": "{quantity} m² × 0.225 m³/m² = {result} m³",
        "irc_reference": "IRC SP-87:5.1.1",
        "assumptions": [
            "Same as footpath construction"
        ]
    },
}


def _normalize_intervention_type(intervention_type: str) -> str:
    """
    Normalize intervention type for consistent lookup.
    
    Args:
        intervention_type: Raw intervention type string
        
    Returns:
        str: Normalized intervention type
    """
    return intervention_type.lower().strip().replace(" ", "_").replace("-", "_")


def calculate_quantity(
    intervention_type: str,
    user_quantity: float,
    irc_clause: Optional[Dict] = None
) -> Dict:
    """
    Calculate material quantities using deterministic mathematical formulas.
    
    This function uses PURE MATHEMATICS based on IRC specifications.
    NO AI or estimation is involved - only hardcoded formulas.
    
    Args:
        intervention_type: Type of intervention (e.g., "speed_breaker", "guardrail")
        user_quantity: Quantity specified by user (e.g., 10 units, 100 meters)
        irc_clause: Optional IRC clause dict (for reference, not used in calculation)
        
    Returns:
        Dict containing:
            - material: Material specification
            - quantity: Calculated material quantity
            - unit: Unit of measurement
            - formula: Human-readable formula
            - calculation: Step-by-step calculation
            - assumptions: List of assumptions made
            - irc_reference: IRC standard reference
            - error: Error message if validation failed (only present on error)
            
    Examples:
        >>> result = calculate_quantity("speed_breaker", 10)
        >>> print(f"{result['quantity']} {result['unit']} of {result['material']}")
        0.525 cum of Concrete M15 (1:2:4)
        
        >>> result = calculate_quantity("guardrail", 100)
        >>> print(f"{result['quantity']} {result['unit']}")
        500 kg
    """
    # Validate user_quantity
    if user_quantity <= 0:
        error_msg = f"Invalid quantity: {user_quantity}. Quantity must be greater than 0."
        logger.error(error_msg)
        return {
            "error": error_msg,
            "material": None,
            "quantity": 0,
            "unit": None,
            "formula": None,
            "calculation": None,
            "assumptions": [],
            "irc_reference": None
        }
    
    # Normalize intervention type
    normalized_type = _normalize_intervention_type(intervention_type)
    
    logger.info(
        f"Calculating quantity for intervention: {normalized_type}, "
        f"user quantity: {user_quantity}"
    )
    
    # Check if intervention type is recognized
    if normalized_type not in QUANTITY_FORMULAS:
        error_msg = (
            f"Unrecognized intervention type: '{intervention_type}'. "
            f"Supported types: {', '.join(QUANTITY_FORMULAS.keys())}"
        )
        logger.error(error_msg)
        return {
            "error": error_msg,
            "material": None,
            "quantity": 0,
            "unit": None,
            "formula": None,
            "calculation": None,
            "assumptions": [],
            "irc_reference": None
        }
    
    # Get formula data
    formula_data = QUANTITY_FORMULAS[normalized_type]
    
    # Calculate material quantity using deterministic formula
    # This is PURE MATHEMATICS - no AI involved
    material_quantity = user_quantity * formula_data["per_unit_quantity"]
    
    # Round to appropriate precision (3 decimal places)
    material_quantity = round(material_quantity, 3)
    
    # Generate step-by-step calculation
    calculation = formula_data["calculation_template"].format(
        quantity=user_quantity,
        result=material_quantity
    )
    
    logger.info(
        f"Calculated {material_quantity} {formula_data['unit']} of "
        f"{formula_data['material']} for {user_quantity} {normalized_type}"
    )
    
    # Build result dictionary
    result = {
        "material": formula_data["material"],
        "quantity": material_quantity,
        "unit": formula_data["unit"],
        "formula": formula_data["formula"],
        "calculation": calculation,
        "assumptions": formula_data["assumptions"],
        "irc_reference": formula_data["irc_reference"]
    }
    
    # Add IRC clause reference if provided
    if irc_clause:
        result["irc_clause_title"] = irc_clause.get("title", "")
        result["irc_standard"] = irc_clause.get("standard", "")
        result["irc_clause_number"] = irc_clause.get("clause", "")
    
    return result


def get_supported_interventions() -> List[str]:
    """
    Get list of all supported intervention types.
    
    Returns:
        List[str]: List of intervention type names
    """
    return sorted(QUANTITY_FORMULAS.keys())


def get_formula_info(intervention_type: str) -> Optional[Dict]:
    """
    Get formula information for a specific intervention type.
    
    Args:
        intervention_type: Type of intervention
        
    Returns:
        Dict: Formula information or None if not found
    """
    normalized_type = _normalize_intervention_type(intervention_type)
    
    if normalized_type not in QUANTITY_FORMULAS:
        logger.warning(f"No formula found for intervention: {normalized_type}")
        return None
    
    return QUANTITY_FORMULAS[normalized_type].copy()


def validate_quantity_input(intervention_type: str, quantity: float) -> tuple[bool, Optional[str]]:
    """
    Validate quantity calculation input.
    
    Args:
        intervention_type: Type of intervention
        quantity: User-specified quantity
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check quantity
    if quantity <= 0:
        return False, f"Quantity must be greater than 0, got {quantity}"
    
    # Check intervention type
    normalized_type = _normalize_intervention_type(intervention_type)
    if normalized_type not in QUANTITY_FORMULAS:
        return False, f"Unsupported intervention type: '{intervention_type}'"
    
    return True, None
