"""FastAPI application for trade reconciliation."""

import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List

from .models import ReconciliationRequest
from .service import ReconciliationService
from ..utils.data_validator import DataValidationError

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Trade Reconciliation API",
    description="Unified reconciliation engine for ICE, SGX, CME, and EEX exchanges",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)

# Add CORS middleware for web clients  
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize service
service = ReconciliationService()


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "trade-reconciliation-api",
        "version": "0.1.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "systems": {
            "ice_match": "available",
            "sgx_match": "available",
            "cme_match": "available",
            "eex_match": "available",
        },
    }


@app.post(
    "/reconcile",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    tags=["Reconciliation"],
)
async def reconcile_trades(request: ReconciliationRequest) -> List[Dict[str, Any]]:
    """
    Process trade reconciliation.

    Accepts trader and exchange trades, routes them to appropriate matching systems
    (ICE, SGX, CME, EEX) based on exchangeGroupId, and returns reconciliation results.

    """
    try:
        result = await service.process_reconciliation(request)
        return result
    except ValueError as e:
        logger.warning(f"Request validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DataValidationError as e:
        logger.warning(f"Data validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration file not found",
        )
    except KeyError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid configuration or missing required data",
        )
    except Exception as e:
        # Log the error internally but don't expose details for security
        logger.error(f"Internal reconciliation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during reconciliation",
        )


# Custom exception handlers removed - handled in endpoint for better control
