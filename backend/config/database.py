"""
MongoDB Database Configuration Module

This module provides functions to connect to MongoDB, manage collections,
and ensure proper indexing for optimal query performance.
"""

import os
import time
import logging
from typing import Optional
from functools import lru_cache

from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Global MongoDB client instance
_mongo_client: Optional[MongoClient] = None
_database: Optional[Database] = None

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Valid collection names
VALID_COLLECTIONS = {"estimates", "irc_clauses", "prices"}


def _create_connection() -> MongoClient:
    """
    Create a new MongoDB client connection.
    
    Returns:
        MongoClient: MongoDB client instance
        
    Raises:
        ValueError: If MONGODB_URL is not set
        ConnectionFailure: If connection fails after all retries
    """
    mongodb_url = os.getenv("MONGODB_URL")
    
    if not mongodb_url:
        logger.error("MONGODB_URL not found in environment variables")
        raise ValueError(
            "MONGODB_URL not found. Please set it in your .env file."
        )
    
    # Get connection pool settings from environment
    max_pool_size = int(os.getenv("MONGODB_MAX_POOL_SIZE", "10"))
    min_pool_size = int(os.getenv("MONGODB_MIN_POOL_SIZE", "1"))
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Attempting to connect to MongoDB (Attempt {attempt}/{MAX_RETRIES})...")
            
            # Create MongoDB client with connection pooling
            client = MongoClient(
                mongodb_url,
                maxPoolSize=max_pool_size,
                minPoolSize=min_pool_size,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,  # 10 second timeout
            )
            
            # Verify connection with ping
            client.admin.command('ping')
            
            logger.info(
                f"Successfully connected to MongoDB with pool size "
                f"(min: {min_pool_size}, max: {max_pool_size})"
            )
            
            return client
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(
                f"MongoDB connection attempt {attempt}/{MAX_RETRIES} failed: {str(e)}"
            )
            
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(
                    f"Failed to connect to MongoDB after {MAX_RETRIES} attempts"
                )
                raise ConnectionFailure(
                    f"Could not connect to MongoDB after {MAX_RETRIES} attempts. "
                    f"Please check your MONGODB_URL and ensure MongoDB is running."
                )
        
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
            raise
    
    raise ConnectionFailure("Failed to establish MongoDB connection")


def get_database() -> Database:
    """
    Get MongoDB database instance with connection pooling.
    
    This function establishes a connection to MongoDB using the URL from
    environment variables, implements connection pooling, and verifies
    the connection with a ping check.
    
    Returns:
        Database: MongoDB database instance
        
    Raises:
        ValueError: If MONGODB_URL or MONGODB_DB_NAME is not set
        ConnectionFailure: If connection fails after retries
    """
    global _mongo_client, _database
    
    # Return existing database connection if available
    if _database is not None:
        try:
            # Verify connection is still alive
            _mongo_client.admin.command('ping')
            return _database
        except Exception as e:
            logger.warning(f"Existing connection lost: {str(e)}. Reconnecting...")
            _mongo_client = None
            _database = None
    
    # Get database name from environment
    db_name = os.getenv("MONGODB_DB_NAME", "brakes_estimator")
    
    if not db_name:
        logger.error("MONGODB_DB_NAME not found in environment variables")
        raise ValueError(
            "MONGODB_DB_NAME not found. Please set it in your .env file."
        )
    
    # Create new connection
    _mongo_client = _create_connection()
    _database = _mongo_client[db_name]
    
    # Create indexes for optimal performance
    _ensure_indexes(_database)
    
    logger.info(f"Using database: {db_name}")
    
    return _database


def get_collection(collection_name: str) -> Collection:
    """
    Get a specific MongoDB collection.
    
    Args:
        collection_name: Name of the collection to retrieve.
                        Valid values: 'estimates', 'irc_clauses', 'prices'
    
    Returns:
        Collection: MongoDB collection instance
        
    Raises:
        ValueError: If collection_name is not valid
    """
    if collection_name not in VALID_COLLECTIONS:
        logger.error(f"Invalid collection name: {collection_name}")
        raise ValueError(
            f"Invalid collection name '{collection_name}'. "
            f"Valid collections are: {', '.join(VALID_COLLECTIONS)}"
        )
    
    db = get_database()
    collection = db[collection_name]
    
    logger.debug(f"Retrieved collection: {collection_name}")
    
    return collection


def _ensure_indexes(database: Database) -> None:
    """
    Create necessary indexes for optimal query performance.
    
    Indexes created:
    - estimates.estimate_id (ascending)
    - prices.material (ascending)
    - irc_clauses.text (text search)
    
    Args:
        database: MongoDB database instance
    """
    try:
        logger.info("Ensuring database indexes...")
        
        # Index on estimates collection
        estimates_collection = database["estimates"]
        estimates_collection.create_index(
            [("estimate_id", ASCENDING)],
            unique=True,
            name="estimate_id_index"
        )
        logger.info("Created index on estimates.estimate_id")
        
        # Index on prices collection
        prices_collection = database["prices"]
        prices_collection.create_index(
            [("material", ASCENDING)],
            name="material_index"
        )
        logger.info("Created index on prices.material")
        
        # Text index on irc_clauses collection for search
        irc_clauses_collection = database["irc_clauses"]
        irc_clauses_collection.create_index(
            [("text", TEXT)],
            name="text_search_index"
        )
        logger.info("Created text index on irc_clauses.text")
        
        logger.info("All database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        # Don't raise - indexes might already exist


def close_connection() -> None:
    """
    Close the MongoDB connection.
    
    This should be called when shutting down the application
    to properly release resources.
    """
    global _mongo_client, _database
    
    if _mongo_client is not None:
        try:
            _mongo_client.close()
            logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {str(e)}")
        finally:
            _mongo_client = None
            _database = None


def check_connection() -> bool:
    """
    Check if MongoDB connection is active and healthy.
    
    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        db = get_database()
        db.client.admin.command('ping')
        logger.info("MongoDB connection is healthy")
        return True
    except Exception as e:
        logger.error(f"MongoDB connection check failed: {str(e)}")
        return False


def get_collection_stats(collection_name: str) -> dict:
    """
    Get statistics for a specific collection.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        dict: Collection statistics including document count, size, etc.
        
    Raises:
        ValueError: If collection_name is not valid
    """
    if collection_name not in VALID_COLLECTIONS:
        raise ValueError(
            f"Invalid collection name '{collection_name}'. "
            f"Valid collections are: {', '.join(VALID_COLLECTIONS)}"
        )
    
    try:
        collection = get_collection(collection_name)
        stats = {
            "name": collection_name,
            "count": collection.count_documents({}),
            "indexes": len(list(collection.list_indexes())),
        }
        logger.debug(f"Retrieved stats for collection '{collection_name}': {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error getting collection stats: {str(e)}")
        return {"name": collection_name, "error": str(e)}


def get_all_collections_stats() -> dict:
    """
    Get statistics for all valid collections.
    
    Returns:
        dict: Statistics for all collections
    """
    stats = {}
    for collection_name in VALID_COLLECTIONS:
        stats[collection_name] = get_collection_stats(collection_name)
    return stats
