from fastapi import APIRouter, Depends
from app.services.market_data import MarketDataService
from app.models.schemas import HealthResponse, MarketStatusResponse

router = APIRouter(prefix="/health", tags=["health"])

market_data_service: MarketDataService = None


def get_market_data_service() -> MarketDataService:
    return market_data_service


@router.get("", response_model=HealthResponse)
async def health_check(service: MarketDataService = Depends(get_market_data_service)):
    return service.get_health()


@router.get("/market", response_model=MarketStatusResponse)
async def market_status(service: MarketDataService = Depends(get_market_data_service)):
    symbol_states = {
        symbol: {
            "connection_state": state.connection_state.value,
            "current_price": state.current_price,
            "mark_price": state.mark_price,
            "index_price": state.index_price,
            "last_tick_time": state.last_tick_time,
        }
        for symbol, state in service.symbol_states.items()
    }
    last_tick = {
        symbol: state.last_tick.model_dump() if state.last_tick else None
        for symbol, state in service.symbol_states.items()
    }
    return MarketStatusResponse(
        mode=service.settings.market_data_mode,
        delta_connection_state=service.get_delta_connection_state(),
        subscribed_symbols=list(service.symbol_states.keys()),
        symbol_states=symbol_states,
        last_tick=last_tick,
    )
