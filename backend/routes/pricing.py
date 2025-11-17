"""
Pricing Route - Material Pricing and Search

This module handles material price lookups, search, and pricing information retrieval.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from services.price_fetcher import (
    get_material_price,
    search_prices,
    get_prices_by_category,
    get_all_categories,
    get_price_statistics,
    load_prices
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/pricing/search", response_model=None)
async def search_material_prices(
    q: str = Query(..., min_length=2, description="Search query for material name"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results to return")
) -> JSONResponse:
    """
    Search for material prices by name.
    
    Performs fuzzy matching to find materials even with slight spelling variations.
    
    Args:
        q: Search query (minimum 2 characters)
        limit: Maximum number of results (1-50, default 10)
        
    Returns:
        JSONResponse: List of matching materials with prices
    """
    logger.info(f"Searching prices for: '{q}' (limit: {limit})")
    
    try:
        results = search_prices(q, limit=limit)
        
        logger.info(f"Found {len(results)} matching materials")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "query": q,
                "count": len(results),
                "results": results
            }
        )
        
    except Exception as e:
        logger.error(f"Error searching prices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search prices: {str(e)}"
        )


@router.get("/pricing/{material_name}", response_model=None)
async def get_material_pricing(material_name: str) -> JSONResponse:
    """
    Get pricing information for a specific material.
    
    Uses exact match first, then falls back to fuzzy matching.
    
    Args:
        material_name: Name of the material
        
    Returns:
        JSONResponse: Material price details
        
    Raises:
        HTTPException: 404 if material not found
    """
    logger.info(f"Fetching price for material: {material_name}")
    
    try:
        price_info = get_material_price(material_name)
        
        if not price_info:
            logger.warning(f"Material not found: {material_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material not found: {material_name}. Try searching with /pricing/search"
            )
        
        logger.info(f"Price found: {material_name} - INR {price_info.get('price_inr', 0)}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "material": price_info
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching material price: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch material price: {str(e)}"
        )


@router.get("/pricing/category/{category_name}", response_model=None)
async def get_category_prices(category_name: str) -> JSONResponse:
    """
    Get all materials in a specific category.
    
    Args:
        category_name: Category name (e.g., "Concrete", "Steel", "Paint & Marking")
        
    Returns:
        JSONResponse: List of materials in the category
        
    Raises:
        HTTPException: 404 if category not found
    """
    logger.info(f"Fetching prices for category: {category_name}")
    
    try:
        materials = get_prices_by_category(category_name)
        
        if not materials:
            logger.warning(f"Category not found or empty: {category_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category not found: {category_name}. Use /pricing/categories to see available categories"
            )
        
        logger.info(f"Found {len(materials)} materials in category: {category_name}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "category": category_name,
                "count": len(materials),
                "materials": materials
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category prices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch category prices: {str(e)}"
        )


@router.get("/pricing/categories", response_model=None)
async def list_categories() -> JSONResponse:
    """
    List all available material categories.
    
    Returns:
        JSONResponse: List of category names
    """
    logger.info("Fetching all categories")
    
    try:
        categories = get_all_categories()
        
        logger.info(f"Found {len(categories)} categories")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "count": len(categories),
                "categories": sorted(categories)
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
        )


@router.get("/pricing/statistics", response_model=None)
async def get_pricing_statistics() -> JSONResponse:
    """
    Get statistical information about the pricing database.
    
    Returns summary statistics including:
    - Total materials count
    - Price ranges by category
    - Average prices
    - Source distribution
    
    Returns:
        JSONResponse: Pricing statistics
    """
    logger.info("Fetching pricing statistics")
    
    try:
        stats = get_price_statistics()
        
        logger.info("Pricing statistics retrieved successfully")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "statistics": stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching pricing statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pricing statistics: {str(e)}"
        )


@router.get("/pricing", response_model=None)
async def list_all_prices(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip")
) -> JSONResponse:
    """
    List all available material prices with pagination.
    
    Args:
        limit: Maximum number of results (1-100, default 50)
        offset: Number of results to skip (default 0)
        
    Returns:
        JSONResponse: Paginated list of all materials
    """
    logger.info(f"Listing all prices: limit={limit}, offset={offset}")
    
    try:
        all_prices = load_prices()
        
        # Convert dict to list
        prices_list = list(all_prices.values())
        
        # Sort by material name
        prices_list.sort(key=lambda x: x.get("material", ""))
        
        # Apply pagination
        total_count = len(prices_list)
        paginated_prices = prices_list[offset:offset + limit]
        
        logger.info(f"Returning {len(paginated_prices)} of {total_count} total materials")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "materials": paginated_prices,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(paginated_prices)) < total_count
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing prices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prices: {str(e)}"
        )
