from fastapi import APIRouter, Depends
from app.services.market_data import MarketDataService
from app.models.schemas import HealthResponse, MarketStatusResponse

router = APIRouter(prefix="/health", tags=["health"])

# Will be set from main.py
market_data_service: MarketDataService = None


def get_market_data_service() -> MarketDataService:
    return market_data_service


@router.get("", response_model=HealthResponse)
async def health_check(service: MarketDataService = Depends(get_market_data_service)):
    return service.get_health()


@router.get("/market", response_model=MarketStatusResponse)
async def market_status(service: MarketDataService = Depends(get_market_data_service)):
    return service.get_status()