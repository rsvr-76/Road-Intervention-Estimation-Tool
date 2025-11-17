"""
Price Fetching Service

This module provides functions to load, search, and fetch material prices
from various sources including CPWD and GeM databases.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from difflib import get_close_matches
import random

# Configure logging
logger = logging.getLogger(__name__)

# Module-level cache for prices
_prices_cache: Optional[Dict[str, Dict]] = None

# Fuzzy matching threshold
FUZZY_MATCH_THRESHOLD = 0.6
FUZZY_MATCH_LIMIT = 3


def _get_prices_file_path() -> str:
    """
    Get the path to the prices JSON file.
    
    Returns:
        str: Absolute path to prices.json
    """
    current_dir = Path(__file__).parent
    prices_file = current_dir.parent / "data" / "prices.json"
    return str(prices_file)


def load_prices() -> Dict[str, Dict]:
    """
    Load material prices from JSON file with in-memory caching.
    
    Prices are loaded once and cached for subsequent calls to avoid
    repeated file I/O operations.
    
    Returns:
        Dict[str, Dict]: Dictionary of materials keyed by material name.
            Each value is a dict containing:
                - material: Material name
                - unit: Unit of measurement
                - price_inr: Price in Indian Rupees
                - source: Price source (e.g., "CPWD SOR 2023")
                - item_code: Item reference code
                - category: Material category
                - fetched_date: Date when price was fetched
                - confidence: Confidence score (0-1)
                - description: Material description
                
    Raises:
        FileNotFoundError: If prices.json is not found
        json.JSONDecodeError: If JSON file is invalid
    """
    global _prices_cache
    
    # Return cached data if available
    if _prices_cache is not None:
        logger.debug("Returning cached prices")
        return _prices_cache
    
    # Load from file
    prices_file = _get_prices_file_path()
    
    if not os.path.exists(prices_file):
        logger.error(f"Prices file not found: {prices_file}")
        raise FileNotFoundError(
            f"Prices data file not found at: {prices_file}. "
            f"Please ensure data/prices.json exists."
        )
    
    try:
        logger.info(f"Loading prices from {prices_file}")
        
        with open(prices_file, 'r', encoding='utf-8') as f:
            prices_list = json.load(f)
        
        if not isinstance(prices_list, list):
            raise ValueError("Prices data must be a JSON array")
        
        # Convert list to dictionary keyed by material name
        prices_dict = {}
        for price_entry in prices_list:
            material_name = price_entry.get("material")
            if not material_name:
                logger.warning("Price entry missing 'material' field, skipping")
                continue
            
            # Normalize material name for consistent lookup
            normalized_name = material_name.lower().strip()
            prices_dict[normalized_name] = price_entry
            
            # Also store with original name for exact matches
            if normalized_name != material_name:
                prices_dict[material_name] = price_entry
        
        # Cache the loaded prices
        _prices_cache = prices_dict
        
        logger.info(f"Successfully loaded {len(prices_list)} material prices")
        return prices_dict
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse prices JSON: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading prices: {str(e)}")
        raise


def clear_cache() -> None:
    """
    Clear the in-memory price cache.
    
    Useful for testing or when the prices file has been updated.
    """
    global _prices_cache
    _prices_cache = None
    logger.info("Prices cache cleared")


def get_material_price(material_name: str) -> Optional[Dict]:
    """
    Get price information for a specific material.
    
    Uses exact matching first, then falls back to fuzzy matching
    if no exact match is found.
    
    Args:
        material_name: Name of the material (e.g., "Concrete M15", "TMT Steel")
        
    Returns:
        Dict: Price information dictionary if found, None otherwise
        
    Example:
        >>> price = get_material_price("Concrete M15")
        >>> print(f"{price['material']}: ₹{price['price_inr']}/{price['unit']}")
        Concrete M15 (1:2:4): ₹5500/cum
    """
    if not material_name or not material_name.strip():
        logger.warning("Empty material name provided")
        return None
    
    logger.debug(f"Looking up price for material: {material_name}")
    
    try:
        prices_dict = load_prices()
    except Exception as e:
        logger.error(f"Failed to load prices: {str(e)}")
        return None
    
    # Normalize material name for lookup
    normalized_name = material_name.lower().strip()
    
    # Try exact match first
    if normalized_name in prices_dict:
        logger.info(f"Found exact match for '{material_name}'")
        return prices_dict[normalized_name].copy()
    
    # Try original name (case-sensitive)
    if material_name in prices_dict:
        logger.info(f"Found case-sensitive match for '{material_name}'")
        return prices_dict[material_name].copy()
    
    # Fuzzy matching fallback
    logger.debug(f"No exact match for '{material_name}', trying fuzzy matching")
    
    all_material_names = list(prices_dict.keys())
    matches = get_close_matches(
        normalized_name,
        all_material_names,
        n=FUZZY_MATCH_LIMIT,
        cutoff=FUZZY_MATCH_THRESHOLD
    )
    
    if matches:
        best_match = matches[0]
        logger.info(
            f"Fuzzy match found: '{material_name}' → '{best_match}' "
            f"(alternatives: {matches[1:] if len(matches) > 1 else 'none'})"
        )
        result = prices_dict[best_match].copy()
        result['fuzzy_match'] = True
        result['original_query'] = material_name
        result['matched_to'] = best_match
        return result
    
    # No match found
    logger.warning(
        f"No price found for material '{material_name}'. "
        f"Available materials: {len(all_material_names)}"
    )
    return None


def fetch_live_cpwd_price(material: str) -> Optional[Dict]:
    """
    Fetch live price from CPWD (Central Public Works Department) database.
    
    TODO: Implement real CPWD API integration
    
    This is currently a MOCK implementation for MVP. In production:
    1. Connect to official CPWD SOR API
    2. Authenticate with API credentials
    3. Query latest rates for the material
    4. Handle rate variations by location/zone
    5. Update local cache periodically
    
    Args:
        material: Material name to query
        
    Returns:
        Dict: Price information with current date, or None if not found
    """
    logger.info(f"Fetching CPWD price for '{material}' (MOCK implementation)")
    
    # TODO: Replace with actual CPWD API call
    # Example API endpoint: https://cpwd.gov.in/api/rates
    # Required: API key, authentication token
    
    # For MVP: Return cached price with current date
    cached_price = get_material_price(material)
    
    if cached_price:
        # Update to current date to simulate live fetch
        cached_price['fetched_date'] = datetime.now().strftime('%Y-%m-%d')
        cached_price['source'] = "CPWD SOR 2024 (Live)"
        cached_price['is_live'] = False  # Flag for mock data
        
        logger.info(
            f"CPWD mock price for '{material}': "
            f"₹{cached_price['price_inr']}/{cached_price['unit']}"
        )
        return cached_price
    
    logger.warning(f"CPWD price not found for material: {material}")
    return None


def fetch_live_gem_price(material: str) -> Optional[Dict]:
    """
    Fetch live price from GeM (Government e-Marketplace) database.
    
    TODO: Implement real GeM API integration
    
    This is currently a MOCK implementation for MVP. In production:
    1. Connect to GeM portal API
    2. Authenticate with organization credentials
    3. Query current market rates
    4. Filter by approved suppliers
    5. Consider delivery time and terms
    
    Args:
        material: Material name to query
        
    Returns:
        Dict: Price information with ±5% variation, or None if not found
    """
    logger.info(f"Fetching GeM price for '{material}' (MOCK implementation)")
    
    # TODO: Replace with actual GeM API call
    # Example API endpoint: https://gem.gov.in/api/products
    # Required: Organization ID, API key, secret
    
    # For MVP: Return cached price with random variation (±5%)
    cached_price = get_material_price(material)
    
    if cached_price:
        # Add random variation to simulate market fluctuation
        base_price = cached_price['price_inr']
        variation = random.uniform(-0.05, 0.05)  # ±5%
        varied_price = round(base_price * (1 + variation), 2)
        
        gem_price = cached_price.copy()
        gem_price['price_inr'] = varied_price
        gem_price['fetched_date'] = datetime.now().strftime('%Y-%m-%d')
        gem_price['source'] = "GeM Portal 2024 (Live)"
        gem_price['is_live'] = False  # Flag for mock data
        gem_price['price_variation'] = f"{variation*100:+.1f}%"
        
        logger.info(
            f"GeM mock price for '{material}': "
            f"₹{varied_price}/{gem_price['unit']} "
            f"({gem_price['price_variation']} from base)"
        )
        return gem_price
    
    logger.warning(f"GeM price not found for material: {material}")
    return None


def merge_prices(
    cpwd_price: Optional[Dict],
    gem_price: Optional[Dict]
) -> Optional[Dict]:
    """
    Merge prices from CPWD and GeM sources.
    
    Strategy:
    - Use CPWD as primary source (government reference)
    - Include GeM price for comparison
    - Flag significant discrepancies (>15%)
    - Calculate confidence score based on agreement
    
    Args:
        cpwd_price: Price data from CPWD source
        gem_price: Price data from GeM source
        
    Returns:
        Dict: Merged price information with both sources and analysis
    """
    # If neither source has data
    if not cpwd_price and not gem_price:
        logger.warning("No price data from either CPWD or GeM")
        return None
    
    # If only one source has data
    if cpwd_price and not gem_price:
        logger.info("Using CPWD price only (GeM unavailable)")
        result = cpwd_price.copy()
        result['price_sources'] = ['CPWD']
        result['confidence'] = 0.90  # Lower confidence without comparison
        return result
    
    if gem_price and not cpwd_price:
        logger.info("Using GeM price only (CPWD unavailable)")
        result = gem_price.copy()
        result['price_sources'] = ['GeM']
        result['confidence'] = 0.85  # Lower confidence without government reference
        result['warning'] = "CPWD reference price not available"
        return result
    
    # Both sources available - merge and compare
    logger.info("Merging prices from both CPWD and GeM")
    
    cpwd_value = cpwd_price['price_inr']
    gem_value = gem_price['price_inr']
    
    # Calculate price discrepancy
    avg_price = (cpwd_value + gem_value) / 2
    discrepancy_percent = abs(cpwd_value - gem_value) / avg_price * 100
    
    # Determine confidence based on agreement
    if discrepancy_percent <= 5:
        confidence = 0.98
        agreement_status = "excellent"
    elif discrepancy_percent <= 10:
        confidence = 0.95
        agreement_status = "good"
    elif discrepancy_percent <= 15:
        confidence = 0.90
        agreement_status = "acceptable"
    else:
        confidence = 0.80
        agreement_status = "poor"
    
    # Build merged result (CPWD as primary)
    merged = cpwd_price.copy()
    merged['price_sources'] = ['CPWD', 'GeM']
    merged['cpwd_price'] = cpwd_value
    merged['gem_price'] = gem_value
    merged['price_discrepancy_percent'] = round(discrepancy_percent, 2)
    merged['price_agreement'] = agreement_status
    merged['confidence'] = confidence
    
    # Add warning for significant discrepancies
    if discrepancy_percent > 15:
        merged['warning'] = (
            f"Significant price discrepancy detected: "
            f"CPWD ₹{cpwd_value} vs GeM ₹{gem_value} "
            f"({discrepancy_percent:.1f}% difference)"
        )
        logger.warning(merged['warning'])
    
    logger.info(
        f"Price merge complete: CPWD ₹{cpwd_value} vs GeM ₹{gem_value} "
        f"(discrepancy: {discrepancy_percent:.1f}%, confidence: {confidence})"
    )
    
    return merged


def search_prices(query: str, limit: int = 10) -> List[Dict]:
    """
    Search for materials by keyword query.
    
    Args:
        query: Search query string
        limit: Maximum number of results
        
    Returns:
        List[Dict]: List of matching price entries
    """
    if not query or not query.strip():
        logger.warning("Empty search query")
        return []
    
    try:
        prices_dict = load_prices()
    except Exception as e:
        logger.error(f"Failed to load prices for search: {str(e)}")
        return []
    
    query_lower = query.lower()
    results = []
    
    for material_key, price_data in prices_dict.items():
        # Search in material name, description, and category
        searchable_text = (
            f"{price_data.get('material', '')} "
            f"{price_data.get('description', '')} "
            f"{price_data.get('category', '')}"
        ).lower()
        
        if query_lower in searchable_text:
            results.append(price_data.copy())
    
    # Remove duplicates (same material stored under multiple keys)
    unique_results = []
    seen_materials = set()
    for result in results:
        material = result.get('material')
        if material not in seen_materials:
            seen_materials.add(material)
            unique_results.append(result)
    
    logger.info(f"Search '{query}' returned {len(unique_results)} results")
    
    return unique_results[:limit]


def get_prices_by_category(category: str) -> List[Dict]:
    """
    Get all prices for a specific category.
    
    Args:
        category: Category name (e.g., "Concrete", "Steel")
        
    Returns:
        List[Dict]: List of price entries in the category
    """
    try:
        prices_dict = load_prices()
    except Exception as e:
        logger.error(f"Failed to load prices: {str(e)}")
        return []
    
    category_lower = category.lower()
    results = []
    seen_materials = set()
    
    for price_data in prices_dict.values():
        material = price_data.get('material')
        price_category = price_data.get('category', '').lower()
        
        if price_category == category_lower and material not in seen_materials:
            seen_materials.add(material)
            results.append(price_data.copy())
    
    logger.info(f"Found {len(results)} materials in category '{category}'")
    return results


def get_all_categories() -> List[str]:
    """
    Get list of all unique categories in the prices database.
    
    Returns:
        List[str]: Sorted list of category names
    """
    try:
        prices_dict = load_prices()
    except Exception as e:
        logger.error(f"Failed to load prices: {str(e)}")
        return []
    
    categories = set()
    for price_data in prices_dict.values():
        category = price_data.get('category')
        if category:
            categories.add(category)
    
    return sorted(categories)


def get_price_statistics() -> Dict:
    """
    Get statistical summary of the prices database.
    
    Returns:
        Dict: Statistics including count, price ranges, etc.
    """
    try:
        prices_dict = load_prices()
    except Exception as e:
        logger.error(f"Failed to load prices: {str(e)}")
        return {}
    
    # Get unique materials
    unique_materials = set()
    prices_list = []
    
    for price_data in prices_dict.values():
        material = price_data.get('material')
        if material and material not in unique_materials:
            unique_materials.add(material)
            prices_list.append(price_data.get('price_inr', 0))
    
    if not prices_list:
        return {}
    
    return {
        "total_materials": len(unique_materials),
        "min_price": min(prices_list),
        "max_price": max(prices_list),
        "avg_price": round(sum(prices_list) / len(prices_list), 2),
        "categories": len(get_all_categories())
    }
