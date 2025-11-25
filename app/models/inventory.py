from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class InventoryItem(BaseModel):
    """재고 상태 항목"""
    product_id: str
    name: str
    current_stock: int = Field(..., ge=0)
    threshold: int = Field(..., ge=0)
    unit_weight: int = Field(..., ge=1, description="제품 1개당 무게(g)")
    last_updated: datetime


class InventoryStatusResponse(BaseModel):
    success: bool = True
    total_items: int
    low_stock_count: int
    items: List[InventoryItem]


class InventoryAlert(BaseModel):
    product_id: str
    name: str
    current_stock: int
    threshold: int
    severity: Literal["warning", "critical"]


class InventoryAlertsResponse(BaseModel):
    success: bool = True
    alerts: List[InventoryAlert]


class InventoryUpdateRequest(BaseModel):
    product_id: str
    new_stock: int = Field(..., ge=0)
    reason: Optional[str] = None
    requested_by: Optional[str] = Field(None, description="재고 변경 요청자")


class InventoryUpdateResponse(BaseModel):
    success: bool = True
    change: int
    item: InventoryItem


class InventorySensorRequest(BaseModel):
    product_id: str
    sensor_id: str
    measured_weight: float = Field(..., ge=0, description="로드셀에서 측정된 무게 (gram)")
    unit: str = Field("g", description="측정 단위 (기본 g)")


class InventorySensorResponse(BaseModel):
    success: bool = True
    product_id: str
    sensor_id: str
    estimated_stock: int
    item: InventoryItem


class InventoryHistoryRecord(BaseModel):
    timestamp: datetime
    product_id: str
    product_name: str
    previous_stock: int
    new_stock: int
    change: int
    source: str
    note: Optional[str] = None


class InventoryHistoryResponse(BaseModel):
    success: bool = True
    history: List[InventoryHistoryRecord]
