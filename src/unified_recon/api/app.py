"""FastAPI application for trade reconciliation."""

import logging
from functools import wraps
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from ..utils.data_validator import DataValidationError
from .models import ReconciliationRequest, Rule0Request, Rule0Response
from .service import PosMatchService, ReconciliationService, Rule0Service

logger = logging.getLogger(__name__)


def handle_api_errors(operation_name: str) -> Callable:
    """
    Decorator to handle common API exceptions with consistent error responses.

    Args:
        operation_name: Name of the operation for logging purposes

    Returns:
        Decorated function with standardized error handling
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ValueError as e:
                logger.warning(f"{operation_name} - Request validation error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
                )
            except DataValidationError as e:
                logger.warning(f"{operation_name} - Data validation error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
                )
            except FileNotFoundError as e:
                logger.error(f"{operation_name} - Configuration file not found: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Configuration file not found",
                )
            except KeyError as e:
                logger.error(f"{operation_name} - Configuration error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid configuration or missing required data",
                )
            except Exception as e:
                # Log the error internally but don't expose details for security
                logger.error(f"{operation_name} - Internal error: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Internal server error during {operation_name.lower()}",
                )

        return wrapper

    return decorator


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

# Initialize services
service = ReconciliationService()
rule0_service = Rule0Service()
posmatch_service = PosMatchService()


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
@handle_api_errors("Reconciliation")
async def reconcile_trades(request: ReconciliationRequest) -> List[Dict[str, Any]]:
    """
    Process trade reconciliation.

    Accepts trader and exchange trades, routes them to appropriate matching systems
    (ICE, SGX, CME, EEX) based on exchangeGroupId, and returns reconciliation results.

    """
    result = await service.process_reconciliation(request)
    return result


@app.post(
    "/poscheck",
    response_model=Rule0Response,
    status_code=status.HTTP_200_OK,
    tags=["Position Check"],
)
@handle_api_errors("Rule 0 analysis")
async def analyze_positions(request: Rule0Request) -> Rule0Response:
    """
    Process position check (Rule 0) decomposition analysis.

    Accepts trader and exchange trades, decomposes complex products (cracks, spreads),
    and returns position analysis with matched/mismatched positions in JSON format.

    This endpoint analyzes positions by:
    - Decomposing crack products into base components
    - Aggregating positions by contract month and product
    - Comparing trader vs exchange positions
    - Identifying matches, mismatches, and missing positions
    """
    result = await rule0_service.process_rule0_analysis(request)
    return result


@app.post(
    "/posmatch",
    response_model=Rule0Response,
    status_code=status.HTTP_200_OK,
    tags=["Position Match"],
)
@handle_api_errors("Position match analysis")
async def analyze_positions_with_match(request: Rule0Request) -> Rule0Response:
    """
    Process position check with reconciliation match IDs.

    Similar to /poscheck but uses actual reconciliation match IDs from the matching engines
    instead of simple position-based matching. This provides:

    - Real match IDs from ICE/SGX/CME/EEX matching rules
    - Position decomposition and aggregation
    - Integration of reconciliation results with position analysis

    The match IDs in the output correspond to actual matched trades from the reconciliation
    engine, providing full traceability between position analysis and trade matching.
    """
    result = await posmatch_service.process_posmatch_analysis(request)
    return result


# Custom exception handlers removed - handled in endpoint for better control
