"""
IRC Clause Retrieval Service

This module provides functions to load, search, and retrieve IRC (Indian Roads Congress)
specification clauses for road safety interventions.
"""

import json
import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
import re

# Configure logging
logger = logging.getLogger(__name__)

# Module-level cache for IRC clauses
_irc_clauses_cache: Optional[List[Dict]] = None

# Intervention type to IRC clause mapping
INTERVENTION_CLAUSE_MAP = {
    "speed_breaker": {"standard": "IRC 67", "clause": "3.2.1"},
    "speed_bump": {"standard": "IRC 67", "clause": "3.2.1"},
    "rumble_strip": {"standard": "IRC 67", "clause": "3.3.1"},
    "guardrail": {"standard": "IRC 35", "clause": "6.1.1"},
    "guard_rail": {"standard": "IRC 35", "clause": "6.1.1"},
    "crash_barrier": {"standard": "IRC 35", "clause": "6.2.1"},
    "barrier": {"standard": "IRC 35", "clause": "6.2.1"},
    "road_marking": {"standard": "IRC 35", "clause": "5.2.1"},
    "pavement_marking": {"standard": "IRC 35", "clause": "5.2.1"},
    "zebra_crossing": {"standard": "IRC 35", "clause": "5.3.1"},
    "pedestrian_crossing": {"standard": "IRC 35", "clause": "5.3.1"},
    "street_light": {"standard": "IRC 99", "clause": "4.2.2"},
    "lighting": {"standard": "IRC 99", "clause": "4.2.2"},
    "road_sign": {"standard": "IRC 99", "clause": "5.1.1"},
    "signage": {"standard": "IRC 99", "clause": "5.1.1"},
    "traffic_sign": {"standard": "IRC 99", "clause": "5.1.1"},
    "warning_sign": {"standard": "IRC 99", "clause": "5.1.2"},
    "direction_sign": {"standard": "IRC 99", "clause": "5.3.1"},
    "traffic_cone": {"standard": "IRC SP-84", "clause": "4.1.1"},
    "barricade": {"standard": "IRC SP-84", "clause": "4.2.1"},
    "traffic_light": {"standard": "IRC SP-84", "clause": "5.2.1"},
    "signal": {"standard": "IRC SP-84", "clause": "5.2.1"},
    "bollard": {"standard": "IRC 35", "clause": "8.2.1"},
    "delineator": {"standard": "IRC 67", "clause": "7.1.1"},
    "footpath": {"standard": "IRC SP-87", "clause": "5.1.1"},
    "sidewalk": {"standard": "IRC SP-87", "clause": "5.1.1"},
    "pedestrian_fence": {"standard": "IRC SP-84", "clause": "8.1.1"},
    "bus_shelter": {"standard": "IRC SP-87", "clause": "6.2.1"},
    "cycle_track": {"standard": "IRC SP-87", "clause": "7.1.1"},
    "parking_bay": {"standard": "IRC SP-87", "clause": "9.1.1"},
}


def _get_data_file_path() -> str:
    """
    Get the path to the IRC clauses JSON file.
    
    Returns:
        str: Absolute path to irc_clauses.json
    """
    # Get the directory where this script is located
    current_dir = Path(__file__).parent
    # Go up one level to backend directory, then into data folder
    data_file = current_dir.parent / "data" / "irc_clauses.json"
    return str(data_file)


def load_irc_clauses() -> List[Dict]:
    """
    Load IRC clauses from JSON file with in-memory caching.
    
    The clauses are loaded once and cached in memory for subsequent calls.
    This avoids repeated file I/O operations.
    
    Returns:
        List[Dict]: List of IRC clause dictionaries, each containing:
            - standard: IRC standard reference (e.g., "IRC 67")
            - clause: Clause number (e.g., "3.2.1")
            - title: Clause title
            - text: Detailed specification text
            - material: Material specification
            - unit: Unit of measurement
            - formula: Calculation formula
            - per_unit_quantity: Quantity per unit
            - category: Category classification
            - page: Page reference
            
    Raises:
        FileNotFoundError: If irc_clauses.json is not found
        json.JSONDecodeError: If JSON file is invalid
    """
    global _irc_clauses_cache
    
    # Return cached data if available
    if _irc_clauses_cache is not None:
        logger.debug("Returning cached IRC clauses")
        return _irc_clauses_cache
    
    # Load from file
    data_file = _get_data_file_path()
    
    if not os.path.exists(data_file):
        logger.error(f"IRC clauses file not found: {data_file}")
        raise FileNotFoundError(
            f"IRC clauses data file not found at: {data_file}. "
            f"Please ensure data/irc_clauses.json exists."
        )
    
    try:
        logger.info(f"Loading IRC clauses from {data_file}")
        
        with open(data_file, 'r', encoding='utf-8') as f:
            clauses = json.load(f)
        
        if not isinstance(clauses, list):
            raise ValueError("IRC clauses data must be a JSON array")
        
        if len(clauses) == 0:
            logger.warning("IRC clauses file is empty")
        
        # Validate each clause has required fields
        required_fields = ["standard", "clause", "title", "material", "unit"]
        for i, clause in enumerate(clauses):
            for field in required_fields:
                if field not in clause:
                    logger.error(
                        f"Clause at index {i} missing required field: {field}"
                    )
                    raise ValueError(
                        f"Invalid clause at index {i}: missing field '{field}'"
                    )
        
        # Cache the loaded clauses
        _irc_clauses_cache = clauses
        
        logger.info(f"Successfully loaded {len(clauses)} IRC clauses")
        return clauses
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse IRC clauses JSON: {str(e)}")
        raise json.JSONDecodeError(
            f"Invalid JSON in IRC clauses file: {str(e)}",
            e.doc,
            e.pos
        )
    except Exception as e:
        logger.error(f"Error loading IRC clauses: {str(e)}")
        raise


def clear_cache() -> None:
    """
    Clear the in-memory cache of IRC clauses.
    
    Useful for testing or when the data file has been updated.
    """
    global _irc_clauses_cache
    _irc_clauses_cache = None
    logger.info("IRC clauses cache cleared")


def get_clause_by_intervention(intervention_type: str) -> Optional[Dict]:
    """
    Get IRC clause for a specific intervention type.
    
    Maps intervention types to their corresponding IRC specifications using
    exact matching. If exact match is found, retrieves the full clause details.
    
    Args:
        intervention_type: Type of intervention (e.g., "speed_breaker", "guardrail")
        
    Returns:
        Dict: Clause dictionary with all metadata if found, None otherwise
        
    Examples:
        >>> clause = get_clause_by_intervention("speed_breaker")
        >>> print(clause['standard'])  # "IRC 67"
        >>> print(clause['clause'])     # "3.2.1"
    """
    if not intervention_type:
        logger.warning("Empty intervention_type provided")
        return None
    
    # Normalize intervention type
    normalized_type = intervention_type.lower().strip().replace(" ", "_").replace("-", "_")
    
    logger.debug(f"Looking up clause for intervention: {normalized_type}")
    
    # Check if intervention type has a mapping
    if normalized_type not in INTERVENTION_CLAUSE_MAP:
        logger.warning(
            f"No clause mapping found for intervention type: {normalized_type}"
        )
        return None
    
    # Get the standard and clause reference
    mapping = INTERVENTION_CLAUSE_MAP[normalized_type]
    target_standard = mapping["standard"]
    target_clause = mapping["clause"]
    
    logger.debug(
        f"Mapped {normalized_type} to {target_standard} clause {target_clause}"
    )
    
    # Load all clauses
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses: {str(e)}")
        return None
    
    # Find matching clause
    for clause in all_clauses:
        if (clause["standard"] == target_standard and 
            clause["clause"] == target_clause):
            logger.info(
                f"Found clause for {normalized_type}: "
                f"{clause['standard']} {clause['clause']} - {clause['title']}"
            )
            return clause
    
    logger.warning(
        f"Clause {target_standard}:{target_clause} not found in database"
    )
    return None


def _calculate_relevance_score(clause: Dict, query_terms: List[str]) -> int:
    """
    Calculate relevance score for a clause based on query terms.
    
    Args:
        clause: Clause dictionary
        query_terms: List of search terms
        
    Returns:
        int: Relevance score (higher is more relevant)
    """
    score = 0
    
    # Search in different fields with different weights
    searchable_text = (
        f"{clause.get('title', '')} "
        f"{clause.get('text', '')} "
        f"{clause.get('category', '')} "
        f"{clause.get('material', '')}"
    ).lower()
    
    for term in query_terms:
        term_lower = term.lower()
        
        # Title match (weight: 5)
        if term_lower in clause.get('title', '').lower():
            score += 5
        
        # Category match (weight: 3)
        if term_lower in clause.get('category', '').lower():
            score += 3
        
        # Material match (weight: 2)
        if term_lower in clause.get('material', '').lower():
            score += 2
        
        # Text match (weight: 1)
        if term_lower in clause.get('text', '').lower():
            score += 1
        
        # Standard match (weight: 2)
        if term_lower in clause.get('standard', '').lower():
            score += 2
    
    return score


def search_clauses(query: str, limit: int = 5) -> List[Dict]:
    """
    Search IRC clauses by keyword query.
    
    Searches through clause titles, text, categories, and materials.
    Returns results ranked by relevance with configurable limit.
    
    Args:
        query: Search query string (keywords)
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        List[Dict]: List of matching clauses, sorted by relevance (most relevant first)
        
    Examples:
        >>> results = search_clauses("speed breaker")
        >>> for clause in results:
        ...     print(f"{clause['standard']} - {clause['title']}")
    """
    if not query or not query.strip():
        logger.warning("Empty search query provided")
        return []
    
    logger.info(f"Searching clauses for: '{query}'")
    
    # Load all clauses
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses for search: {str(e)}")
        return []
    
    # Split query into terms
    query_terms = re.split(r'[\s,]+', query.strip())
    query_terms = [term for term in query_terms if len(term) > 2]  # Filter short terms
    
    if not query_terms:
        logger.warning("No valid search terms after processing")
        return []
    
    logger.debug(f"Search terms: {query_terms}")
    
    # Calculate relevance scores
    scored_clauses = []
    for clause in all_clauses:
        score = _calculate_relevance_score(clause, query_terms)
        if score > 0:
            scored_clauses.append((score, clause))
    
    # Sort by score (descending) and limit results
    scored_clauses.sort(key=lambda x: x[0], reverse=True)
    results = [clause for score, clause in scored_clauses[:limit]]
    
    logger.info(
        f"Search returned {len(results)} results "
        f"(from {len(scored_clauses)} matches)"
    )
    
    return results


def get_clauses_by_category(category: str) -> List[Dict]:
    """
    Get all IRC clauses for a specific category.
    
    Args:
        category: Category name (e.g., "Speed Control", "Crash Barrier")
        
    Returns:
        List[Dict]: List of clauses in the specified category
    """
    if not category:
        logger.warning("Empty category provided")
        return []
    
    logger.debug(f"Getting clauses for category: {category}")
    
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses: {str(e)}")
        return []
    
    # Filter by category (case-insensitive)
    category_lower = category.lower()
    results = [
        clause for clause in all_clauses
        if clause.get('category', '').lower() == category_lower
    ]
    
    logger.info(f"Found {len(results)} clauses in category '{category}'")
    return results


def get_clauses_by_standard(standard: str) -> List[Dict]:
    """
    Get all clauses for a specific IRC standard.
    
    Args:
        standard: IRC standard (e.g., "IRC 67", "IRC SP-84")
        
    Returns:
        List[Dict]: List of clauses from the specified standard
    """
    if not standard:
        logger.warning("Empty standard provided")
        return []
    
    logger.debug(f"Getting clauses for standard: {standard}")
    
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses: {str(e)}")
        return []
    
    # Filter by standard
    results = [
        clause for clause in all_clauses
        if clause.get('standard', '') == standard
    ]
    
    logger.info(f"Found {len(results)} clauses in standard '{standard}'")
    return results


def get_all_categories() -> List[str]:
    """
    Get list of all unique categories in the IRC clauses database.
    
    Returns:
        List[str]: Sorted list of category names
    """
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses: {str(e)}")
        return []
    
    categories = set(clause.get('category', '') for clause in all_clauses)
    categories = [cat for cat in categories if cat]  # Remove empty strings
    
    return sorted(categories)


def get_all_standards() -> List[str]:
    """
    Get list of all unique IRC standards in the database.
    
    Returns:
        List[str]: Sorted list of standard names
    """
    try:
        all_clauses = load_irc_clauses()
    except Exception as e:
        logger.error(f"Failed to load IRC clauses: {str(e)}")
        return []
    
    standards = set(clause.get('standard', '') for clause in all_clauses)
    standards = [std for std in standards if std]  # Remove empty strings
    
    return sorted(standards)
