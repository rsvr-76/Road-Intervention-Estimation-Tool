"""
BRAKES Road Intervention Estimator - FastAPI Application

This is the main FastAPI application that provides REST APIs for:
- PDF upload and text extraction
- Intervention parsing from text
- Cost estimation using IRC specifications
- Material pricing from CPWD/GeM databases
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from dotenv import load_dotenv

# Import configuration modules
from config.database import get_database, close_connection, check_connection
from config.gemini import initialize_gemini

# Import services to initialize caches
from services.clause_retriever import load_irc_clauses
from services.price_fetcher import load_prices

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Sentry for error monitoring
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info(f"Sentry initialized for environment: {SENTRY_ENVIRONMENT}")
else:
    logger.warning("Sentry DSN not configured. Error monitoring disabled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Startup:
    - Initialize database connection
    - Load IRC clauses cache
    - Load material prices cache
    - Initialize Gemini API client
    
    Shutdown:
    - Close database connections
    - Clear caches
    """
    logger.info("Starting up BRAKES application...")
    
    # Startup tasks
    try:
        # Initialize database
        logger.info("Initializing database connection...")
        db = get_database()
        if db is not None:
            logger.info("Database connection established")
        else:
            logger.error("Failed to establish database connection")
        
        # Check database connection
        is_connected, message = check_connection()
        if is_connected:
            logger.info(f"Database check: {message}")
        else:
            logger.error(f"Database check failed: {message}")
        
        # Load IRC clauses into memory
        logger.info("Loading IRC clauses...")
        irc_clauses = load_irc_clauses()
        logger.info(f"Loaded {len(irc_clauses)} IRC clauses")
        
        # Load material prices into memory
        logger.info("Loading material prices...")
        prices = load_prices()
        logger.info(f"Loaded {len(prices)} material prices")
        
        # Initialize Gemini API
        logger.info("Initializing Gemini API...")
        gemini_model = initialize_gemini()
        if gemini_model:
            logger.info("Gemini API initialized successfully")
        else:
            logger.warning("Gemini API initialization failed")
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        # Don't raise - allow app to start even if some services fail
    
    yield  # Application runs
    
    # Shutdown tasks
    logger.info("Shutting down BRAKES application...")
    
    try:
        # Close database connection
        logger.info("Closing database connection...")
        close_connection()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="BRAKES Road Intervention Estimator",
    description=(
        "AI-powered material cost estimation for road safety interventions. "
        "Uses IRC specifications, CPWD pricing, and Gemini AI for accurate estimates."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for origins: {CORS_ORIGINS}")


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all incoming requests with timing information.
    """
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = round(time.time() - start_time, 3)
    
    # Log response
    logger.info(
        f"Response: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time}s"
    )
    
    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions with consistent JSON response format.
    """
    logger.warning(
        f"HTTP {exc.status_code} on {request.method} {request.url.path}: "
        f"{exc.detail}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
            "path": str(request.url.path)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors with detailed error messages.
    """
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: "
        f"{exc.errors()}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status_code": 422,
            "message": "Request validation failed",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions with error logging and Sentry reporting.
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{str(exc)}",
        exc_info=True
    )
    
    # Report to Sentry if configured
    if SENTRY_DSN:
        sentry_sdk.capture_exception(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": 500,
            "message": "Internal server error",
            "details": str(exc) if os.getenv("APP_ENV") == "development" else None,
            "path": str(request.url.path)
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Check the health of the application and its dependencies.
    
    Returns:
        Dict: Health status of all components
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "services": {}
    }
    
    # Check database
    db_connected, db_message = check_connection()
    health_status["services"]["database"] = {
        "status": "healthy" if db_connected else "unhealthy",
        "message": db_message
    }
    
    # Check IRC clauses
    try:
        irc_clauses = load_irc_clauses()
        health_status["services"]["irc_clauses"] = {
            "status": "healthy",
            "count": len(irc_clauses)
        }
    except Exception as e:
        health_status["services"]["irc_clauses"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check material prices
    try:
        prices = load_prices()
        health_status["services"]["material_prices"] = {
            "status": "healthy",
            "count": len(prices)
        }
    except Exception as e:
        health_status["services"]["material_prices"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Gemini API
    try:
        gemini_model = initialize_gemini()
        health_status["services"]["gemini_api"] = {
            "status": "healthy" if gemini_model else "unhealthy",
            "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        }
    except Exception as e:
        health_status["services"]["gemini_api"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Overall status
    unhealthy_services = [
        name for name, service in health_status["services"].items()
        if service["status"] == "unhealthy"
    ]
    
    if unhealthy_services:
        health_status["status"] = "unhealthy"
        health_status["unhealthy_services"] = unhealthy_services
    
    # Return appropriate status code
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """
    Root endpoint with API information.
    """
    return {
        "name": "BRAKES Road Intervention Estimator API",
        "version": "1.0.0",
        "description": "AI-powered material cost estimation for road safety interventions",
        "docs": "/api/docs",
        "health": "/health"
    }


# Import route modules
from routes import upload, estimate, pricing

# Include routers
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(estimate.router, prefix="/api", tags=["Estimate"])
app.include_router(pricing.router, prefix="/api", tags=["Pricing"])


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    reload = os.getenv("APP_ENV", "development") == "development"
    
    logger.info(f"Starting server on {host}:{port} (reload={reload})")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
