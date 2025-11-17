"""
Intervention Parsing Service

This module provides intelligent parsing of road safety interventions from text
using Gemini AI with keyword-based fallback for robustness.
"""

import json
import re
import logging
from typing import List, Optional, Dict, Any, Tuple

from models.intervention import Intervention, InterventionType
from config.gemini import call_gemini

# Configure logging
logger = logging.getLogger(__name__)

# System instruction for Gemini
GEMINI_SYSTEM_INSTRUCTION = """You are an expert at extracting road safety intervention information from documents.

Extract all road safety interventions mentioned in the text and return ONLY a valid JSON array.

Valid intervention types:
- speed_breaker
- rumble_strip
- road_marking
- signage
- guardrail
- traffic_light
- pedestrian_crossing
- barrier
- pavement

For each intervention, extract:
- type: intervention type (use one of the valid types above)
- quantity: numeric quantity
- unit: unit of measurement (units, meters, square_meters, linear_meters, km, etc.)
- location: location or chainage information (optional)

Return ONLY the JSON array, no additional text or explanation.

Example output:
[
  {"type": "speed_breaker", "quantity": 5, "unit": "units", "location": "km 4.5 to 8.2"},
  {"type": "guardrail", "quantity": 200, "unit": "meters", "location": "highway section A"},
  {"type": "road_marking", "quantity": 1500, "unit": "square_meters", "location": "entire stretch"}
]"""

# Keyword patterns for fallback extraction
INTERVENTION_KEYWORDS = {
    "speed_breaker": [
        r"speed\s+breaker?s?",
        r"speed\s+bump?s?",
        r"traffic\s+calming",
        r"rumble\s+strip?s?"
    ],
    "guardrail": [
        r"guard\s*rail?s?",
        r"crash\s+barrier?s?",
        r"safety\s+barrier?s?",
        r"railing?s?"
    ],
    "road_marking": [
        r"road\s+marking?s?",
        r"pavement\s+marking?s?",
        r"lane\s+marking?s?",
        r"zebra\s+crossing?s?"
    ],
    "signage": [
        r"sign\s*board?s?",
        r"traffic\s+sign?s?",
        r"road\s+sign?s?",
        r"warning\s+sign?s?"
    ],
    "traffic_light": [
        r"traffic\s+light?s?",
        r"signal?s?",
        r"traffic\s+signal?s?"
    ],
    "street_light": [
        r"street\s+light?s?",
        r"lamp\s+post?s?",
        r"lighting",
        r"illumination"
    ],
    "pedestrian_crossing": [
        r"pedestrian\s+crossing?s?",
        r"crosswalk?s?",
        r"zebra\s+crossing?s?"
    ],
    "barrier": [
        r"barrier?s?",
        r"bollard?s?",
        r"concrete\s+barrier?s?"
    ]
}

# Unit patterns
UNIT_PATTERNS = {
    "units": r"\b(unit?s?|no?s?|number?s?)\b",
    "meters": r"\b(meter?s?|metre?s?|m|linear\s+meter?s?)\b",
    "square_meters": r"\b(sq\.?\s*m|square\s+meter?s?|sqm|m2|m²)\b",
    "kilometers": r"\b(km|kilometer?s?|kilometre?s?)\b",
    "linear_meters": r"\b(l\.?m|linear\s+meter?s?|running\s+meter?s?)\b"
}


def _extract_json_from_text(text: str) -> Optional[List[Dict]]:
    """
    Extract JSON array from text that may contain additional content.
    
    Args:
        text: Text potentially containing JSON
        
    Returns:
        List of dictionaries if valid JSON found, None otherwise
    """
    # Try to find JSON array in the text
    json_pattern = r'\[[\s\S]*?\]'
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            continue
    
    # Try parsing the entire text as JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    
    return None


def _validate_intervention_data(data: Dict) -> bool:
    """
    Validate intervention data before creating Intervention object.
    
    Args:
        data: Dictionary containing intervention data
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ["type", "quantity", "unit"]
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return False
    
    # Validate quantity
    try:
        quantity = float(data["quantity"])
        if quantity <= 0:
            logger.warning(f"Invalid quantity: {quantity} (must be > 0)")
            return False
    except (ValueError, TypeError):
        logger.warning(f"Invalid quantity value: {data['quantity']}")
        return False
    
    # Validate type
    intervention_type = str(data["type"]).lower().strip()
    valid_types = [e.value for e in InterventionType]
    if intervention_type not in valid_types and intervention_type != "other":
        logger.warning(
            f"Unknown intervention type: {intervention_type} "
            f"(will be normalized)"
        )
    
    return True


def parse_with_gemini(text: str) -> List[Intervention]:
    """
    Parse interventions from text using Gemini AI.
    
    Sends the text to Gemini with specific instructions to extract
    road safety interventions and return structured JSON data.
    
    Args:
        text: Text containing intervention information
        
    Returns:
        List[Intervention]: List of parsed interventions with confidence=0.92
    """
    if not text or len(text.strip()) < 10:
        logger.warning("Text too short for Gemini parsing")
        return []
    
    logger.info(f"Parsing interventions with Gemini (text length: {len(text)})")
    
    try:
        # Create prompt
        prompt = f"""Extract road safety interventions from the following text:

{text}

Remember to return ONLY a valid JSON array."""
        
        # Call Gemini
        response = call_gemini(prompt, GEMINI_SYSTEM_INSTRUCTION)
        
        if not response:
            logger.error("Gemini returned empty response")
            return []
        
        logger.debug(f"Gemini response: {response[:200]}...")
        
        # Extract JSON from response
        intervention_data = _extract_json_from_text(response)
        
        if not intervention_data:
            logger.error("Failed to extract valid JSON from Gemini response")
            return []
        
        # Parse interventions
        interventions = []
        for item in intervention_data:
            if not _validate_intervention_data(item):
                continue
            
            try:
                intervention = Intervention(
                    type=str(item["type"]),
                    quantity=float(item["quantity"]),
                    unit=str(item["unit"]),
                    location=item.get("location"),
                    confidence=0.92,
                    extraction_method="gemini"
                )
                interventions.append(intervention)
                logger.debug(
                    f"Parsed intervention: {intervention.type} - "
                    f"{intervention.quantity} {intervention.unit}"
                )
            except Exception as e:
                logger.error(f"Failed to create Intervention object: {str(e)}")
                continue
        
        logger.info(f"Successfully parsed {len(interventions)} interventions with Gemini")
        return interventions
        
    except Exception as e:
        logger.error(f"Gemini parsing failed: {str(e)}")
        return []


def _extract_quantity_near_keyword(text: str, keyword_pos: int) -> Optional[float]:
    """
    Extract numeric quantity near a keyword position.
    
    Args:
        text: Full text
        keyword_pos: Position of the keyword
        
    Returns:
        float: Extracted quantity or None
    """
    # Look for numbers within 100 characters before or after keyword
    search_start = max(0, keyword_pos - 100)
    search_end = min(len(text), keyword_pos + 100)
    search_text = text[search_start:search_end]
    
    # Find all numbers in the vicinity
    number_pattern = r'\b(\d+(?:\.\d+)?)\b'
    matches = re.finditer(number_pattern, search_text)
    
    for match in matches:
        try:
            quantity = float(match.group(1))
            if 0 < quantity < 100000:  # Reasonable range
                return quantity
        except ValueError:
            continue
    
    return None


def _extract_location_near_keyword(text: str, keyword_pos: int) -> Optional[str]:
    """
    Extract location information near a keyword position.
    
    Args:
        text: Full text
        keyword_pos: Position of the keyword
        
    Returns:
        str: Extracted location or None
    """
    # Look for location patterns
    location_patterns = [
        r'km\s+\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?',
        r'chainage\s+\d+\+\d+',
        r'section\s+[A-Z\d]+',
        r'from\s+[^,\n]+\s+to\s+[^,\n]+',
    ]
    
    search_start = max(0, keyword_pos - 150)
    search_end = min(len(text), keyword_pos + 150)
    search_text = text[search_start:search_end]
    
    for pattern in location_patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    return None


def _infer_unit(intervention_type: str, text_context: str) -> str:
    """
    Infer the most likely unit for an intervention type.
    
    Args:
        intervention_type: Type of intervention
        text_context: Surrounding text context
        
    Returns:
        str: Inferred unit
    """
    # Check for explicit unit mentions in context
    for unit, pattern in UNIT_PATTERNS.items():
        if re.search(pattern, text_context, re.IGNORECASE):
            return unit
    
    # Default units by intervention type
    default_units = {
        "speed_breaker": "units",
        "rumble_strip": "units",
        "guardrail": "meters",
        "road_marking": "square_meters",
        "signage": "units",
        "traffic_light": "units",
        "street_light": "units",
        "pedestrian_crossing": "units",
        "barrier": "meters",
        "pavement": "square_meters"
    }
    
    return default_units.get(intervention_type, "units")


def parse_with_keywords(text: str) -> List[Intervention]:
    """
    Parse interventions using keyword-based extraction (fallback method).
    
    Searches for predefined keywords and extracts quantity, unit, and location
    information from the surrounding context.
    
    Args:
        text: Text containing intervention information
        
    Returns:
        List[Intervention]: List of parsed interventions with confidence=0.65
    """
    if not text or len(text.strip()) < 10:
        logger.warning("Text too short for keyword parsing")
        return []
    
    logger.info(f"Parsing interventions with keywords (text length: {len(text)})")
    
    interventions = []
    text_lower = text.lower()
    
    for intervention_type, patterns in INTERVENTION_KEYWORDS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            
            for match in matches:
                keyword_pos = match.start()
                
                # Extract quantity
                quantity = _extract_quantity_near_keyword(text, keyword_pos)
                if not quantity:
                    logger.debug(
                        f"No quantity found for {intervention_type} at position {keyword_pos}"
                    )
                    continue
                
                # Extract location
                location = _extract_location_near_keyword(text, keyword_pos)
                
                # Get context for unit inference
                context_start = max(0, keyword_pos - 100)
                context_end = min(len(text), keyword_pos + 100)
                context = text[context_start:context_end]
                
                # Infer unit
                unit = _infer_unit(intervention_type, context)
                
                try:
                    intervention = Intervention(
                        type=intervention_type,
                        quantity=quantity,
                        unit=unit,
                        location=location,
                        confidence=0.65,
                        extraction_method="ocr"
                    )
                    interventions.append(intervention)
                    logger.debug(
                        f"Extracted intervention: {intervention_type} - "
                        f"{quantity} {unit} at {location or 'unknown location'}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create Intervention: {str(e)}")
                    continue
    
    logger.info(f"Extracted {len(interventions)} interventions using keywords")
    return interventions


def _remove_duplicates(interventions: List[Intervention]) -> List[Intervention]:
    """
    Remove duplicate interventions, keeping the one with higher confidence.
    
    Args:
        interventions: List of interventions
        
    Returns:
        List[Intervention]: Deduplicated list
    """
    if not interventions:
        return []
    
    # Group by type and similar quantity (within 10% tolerance)
    unique_interventions = []
    seen = set()
    
    for intervention in interventions:
        # Create a key for deduplication
        key = (
            intervention.type,
            round(intervention.quantity / 10) * 10,  # Round to nearest 10
            intervention.unit
        )
        
        if key not in seen:
            seen.add(key)
            unique_interventions.append(intervention)
        else:
            # Check if this one has higher confidence
            for i, existing in enumerate(unique_interventions):
                existing_key = (
                    existing.type,
                    round(existing.quantity / 10) * 10,
                    existing.unit
                )
                if existing_key == key and intervention.confidence > existing.confidence:
                    unique_interventions[i] = intervention
                    break
    
    logger.info(
        f"Removed {len(interventions) - len(unique_interventions)} duplicates"
    )
    return unique_interventions


def parse_interventions(text: str) -> List[Intervention]:
    """
    Parse interventions using hybrid approach with Gemini and keyword fallback.
    
    Main parsing pipeline:
    1. Try Gemini AI first (high accuracy)
    2. If Gemini fails or returns few results, try keyword matching
    3. Merge results and remove duplicates
    4. Return sorted by confidence (highest first)
    
    Args:
        text: Text containing intervention information
        
    Returns:
        List[Intervention]: Sorted list of unique interventions
    """
    if not text or len(text.strip()) < 10:
        logger.warning("Text is empty or too short")
        return []
    
    logger.info("Starting intervention parsing pipeline")
    
    all_interventions = []
    
    # Try Gemini first
    try:
        gemini_results = parse_with_gemini(text)
        if gemini_results:
            all_interventions.extend(gemini_results)
            logger.info(f"Gemini extracted {len(gemini_results)} interventions")
        else:
            logger.warning("Gemini returned no results")
    except Exception as e:
        logger.error(f"Gemini parsing error: {str(e)}")
    
    # Try keyword matching as fallback or supplement
    try:
        keyword_results = parse_with_keywords(text)
        if keyword_results:
            all_interventions.extend(keyword_results)
            logger.info(f"Keyword extraction found {len(keyword_results)} interventions")
        else:
            logger.warning("Keyword extraction returned no results")
    except Exception as e:
        logger.error(f"Keyword parsing error: {str(e)}")
    
    # If no results from either method
    if not all_interventions:
        logger.warning("No interventions could be extracted from text")
        return []
    
    # Remove duplicates
    unique_interventions = _remove_duplicates(all_interventions)
    
    # Sort by confidence (highest first)
    sorted_interventions = sorted(
        unique_interventions,
        key=lambda x: x.confidence,
        reverse=True
    )
    
    logger.info(
        f"Parsing complete: {len(sorted_interventions)} unique interventions found"
    )
    
    # Log summary
    for intervention in sorted_interventions:
        logger.debug(
            f"  - {intervention.type}: {intervention.quantity} {intervention.unit} "
            f"(confidence: {intervention.confidence:.2f}, method: {intervention.extraction_method})"
        )
    
    return sorted_interventions
