from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.inventory import (
    InventoryHistoryResponse,
    InventorySensorRequest,
    InventorySensorResponse,
    InventoryStatusResponse,
    InventoryAlertsResponse,
    InventoryUpdateRequest,
    InventoryUpdateResponse,
)
from app.services.inventory_service import inventory_service

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get(
    "/status",
    response_model=InventoryStatusResponse,
    summary="재고 현황 조회",
)
async def get_inventory_status():
    return inventory_service.get_status()


@router.get(
    "/alerts",
    response_model=InventoryAlertsResponse,
    summary="재고 부족 알림 조회",
)
async def get_inventory_alerts():
    return inventory_service.get_alerts()


@router.post(
    "/update",
    response_model=InventoryUpdateResponse,
    summary="수동 재고 업데이트",
)
async def update_inventory(request: InventoryUpdateRequest):
    try:
        return inventory_service.update_stock(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/sensors",
    response_model=InventorySensorResponse,
    summary="센서 측정값 반영 (HTTP Bridge)",
    description="MQTT 연동 전까지 로드셀 데이터를 HTTP POST로 전달합니다.",
)
async def apply_sensor_data(request: InventorySensorRequest):
    try:
        return inventory_service.apply_sensor_measurement(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/history",
    response_model=InventoryHistoryResponse,
    summary="재고 변동 이력",
)
async def get_inventory_history(
    product_id: Optional[str] = Query(None, description="특정 상품 ID 필터"),
    limit: int = Query(50, ge=1, le=200, description="가져올 이력 개수"),
):
    return inventory_service.get_history(product_id=product_id, limit=limit)
