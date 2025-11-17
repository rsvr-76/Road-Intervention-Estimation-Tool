"""
Gemini API Configuration Module

This module provides functions to interact with Google's Generative AI (Gemini) API.
It includes rate limiting, caching, retry logic, and comprehensive error handling.
"""

import os
import time
import hashlib
import logging
from typing import Optional, Dict
from functools import wraps
from datetime import datetime, timedelta

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW = 60  # seconds
request_timestamps: list[float] = []

# Response cache
response_cache: Dict[str, str] = {}

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds
TIMEOUT = 10  # seconds


def _check_rate_limit() -> None:
    """
    Check if rate limit has been exceeded.
    
    Implements a sliding window rate limiter that allows
    RATE_LIMIT_MAX_REQUESTS requests per RATE_LIMIT_WINDOW seconds.
    
    Raises:
        Exception: If rate limit is exceeded, waits and retries.
    """
    global request_timestamps
    
    current_time = time.time()
    # Remove timestamps outside the current window
    request_timestamps = [
        ts for ts in request_timestamps 
        if current_time - ts < RATE_LIMIT_WINDOW
    ]
    
    if len(request_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        # Calculate wait time until oldest request expires
        oldest_timestamp = request_timestamps[0]
        wait_time = RATE_LIMIT_WINDOW - (current_time - oldest_timestamp)
        
        if wait_time > 0:
            logger.warning(
                f"Rate limit exceeded. Waiting {wait_time:.2f} seconds..."
            )
            time.sleep(wait_time + 0.1)  # Add small buffer
            # Recursively check again after waiting
            _check_rate_limit()
    
    # Record this request
    request_timestamps.append(time.time())


def _generate_cache_key(prompt: str, system_instruction: str) -> str:
    """
    Generate a cache key using SHA-256 hash of prompt and system instruction.
    
    Args:
        prompt: The user prompt
        system_instruction: The system instruction
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    combined = f"{prompt}|{system_instruction}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def initialize_gemini() -> genai.GenerativeModel:
    """
    Initialize and configure the Gemini generative model.
    
    Loads the API key from environment variables, configures the Google
    Generative AI client, and returns a configured model instance.
    
    Returns:
        genai.GenerativeModel: Configured Gemini model instance
        
    Raises:
        ValueError: If GEMINI_API_KEY is not set or invalid
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        raise ValueError(
            "GEMINI_API_KEY not found. Please set it in your .env file."
        )
    
    if not api_key.strip() or api_key == "your-gemini-api-key-here":
        logger.error("Invalid GEMINI_API_KEY detected")
        raise ValueError(
            "Invalid GEMINI_API_KEY. Please set a valid API key in your .env file."
        )
    
    try:
        # Configure the API key
        genai.configure(api_key=api_key)
        
        # Get model name from environment or use default
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        
        # Create generation configuration
        generation_config = GenerationConfig(
            temperature=0,
            max_output_tokens=500,
        )
        
        # Initialize the model
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
        )
        
        logger.info(f"Gemini model '{model_name}' initialized successfully")
        return model
        
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {str(e)}")
        raise ValueError(f"Failed to initialize Gemini: {str(e)}")


def call_gemini(
    prompt: str,
    system_instruction: str = "You are a helpful AI assistant."
) -> Optional[str]:
    """
    Send a prompt to Gemini API with retry logic and caching.
    
    This function implements:
    - Rate limiting (15 requests per minute)
    - Response caching using SHA-256 hash
    - Retry logic with exponential backoff (3 attempts)
    - Comprehensive error handling and logging
    
    Args:
        prompt: The user prompt to send to Gemini
        system_instruction: System instruction to guide model behavior
        
    Returns:
        str: The generated response text, or None if all retries failed
        
    Raises:
        ValueError: If API key is invalid
        TimeoutError: If request exceeds timeout threshold
    """
    # Check cache first
    cache_key = _generate_cache_key(prompt, system_instruction)
    if cache_key in response_cache:
        logger.info("Returning cached response")
        return response_cache[cache_key]
    
    # Log the request
    start_time = time.time()
    logger.info(
        f"Gemini API call initiated - Prompt length: {len(prompt)} characters"
    )
    
    # Retry loop with exponential backoff
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Check rate limit before making request
            _check_rate_limit()
            
            # Initialize model with system instruction
            model = initialize_gemini()
            
            # Start generation with timeout tracking
            request_start = time.time()
            
            # Generate content
            response = model.generate_content(
                f"{system_instruction}\n\nUser: {prompt}"
            )
            
            request_duration = time.time() - request_start
            
            # Check for timeout
            if request_duration > TIMEOUT:
                logger.error(
                    f"Request exceeded timeout ({request_duration:.2f}s > {TIMEOUT}s)"
                )
                raise TimeoutError(
                    f"Gemini API request timed out after {request_duration:.2f} seconds"
                )
            
            # Validate response
            if not response or not response.text:
                logger.error("Received invalid response from Gemini API")
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {backoff} seconds... (Attempt {attempt}/{MAX_RETRIES})")
                    time.sleep(backoff)
                    continue
                return None
            
            # Extract response text
            response_text = response.text.strip()
            
            # Calculate token usage (approximate)
            prompt_tokens = len(prompt.split())
            response_tokens = len(response_text.split())
            total_tokens = prompt_tokens + response_tokens
            
            # Log successful request
            total_time = time.time() - start_time
            logger.info(
                f"Gemini API call successful - "
                f"Response time: {total_time:.2f}s, "
                f"Tokens used (approx): {total_tokens} "
                f"(prompt: {prompt_tokens}, response: {response_tokens})"
            )
            
            # Cache the response
            response_cache[cache_key] = response_text
            
            return response_text
            
        except ValueError as e:
            # Don't retry on invalid API key
            logger.error(f"Invalid API key: {str(e)}")
            raise
            
        except TimeoutError as e:
            # Don't retry on timeout
            logger.error(f"Timeout error: {str(e)}")
            raise
            
        except Exception as e:
            logger.error(
                f"Attempt {attempt}/{MAX_RETRIES} failed: {str(e)}"
            )
            
            if attempt < MAX_RETRIES:
                # Exponential backoff
                backoff = INITIAL_BACKOFF * (2 ** (attempt - 1))
                logger.info(
                    f"Retrying in {backoff} seconds... "
                    f"(Attempt {attempt}/{MAX_RETRIES})"
                )
                time.sleep(backoff)
            else:
                logger.error(
                    f"All {MAX_RETRIES} retry attempts failed. "
                    f"Last error: {str(e)}"
                )
                return None
    
    return None


def clear_cache() -> None:
    """Clear the response cache."""
    global response_cache
    response_cache.clear()
    logger.info("Response cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """
    Get cache statistics.
    
    Returns:
        Dict containing cache size and other metrics
    """
    return {
        "cache_size": len(response_cache),
        "cached_responses": len(response_cache),
    }


def reset_rate_limiter() -> None:
    """Reset the rate limiter (useful for testing)."""
    global request_timestamps
    request_timestamps.clear()
    logger.info("Rate limiter reset")
