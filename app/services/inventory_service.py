from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

from app.models.inventory import (
    InventoryAlertsResponse,
    InventoryAlert,
    InventoryHistoryRecord,
    InventoryHistoryResponse,
    InventoryItem,
    InventorySensorRequest,
    InventorySensorResponse,
    InventoryStatusResponse,
    InventoryUpdateRequest,
    InventoryUpdateResponse,
)


class InventoryService:
    """재고 상태 및 이력 관리 서비스 (임시 인메모리 구현)"""

    def __init__(self) -> None:
        self._items: Dict[str, InventoryItem] = {}
        self._history: List[InventoryHistoryRecord] = []
        self._lock = Lock()
        self._seed_inventory()

    def _seed_inventory(self) -> None:
        now = datetime.utcnow()
        initial_items = [
            InventoryItem(
                product_id="prod_1",
                name="퐁즈 클리어 훼이셜 립&아이 리무버",
                current_stock=120,
                threshold=15,
                unit_weight=120,
                last_updated=now,
            ),
            InventoryItem(
                product_id="prod_2",
                name="닥터지 레드 블레미쉬 수딩크림",
                current_stock=45,
                threshold=20,
                unit_weight=50,
                last_updated=now,
            ),
            InventoryItem(
                product_id="prod_3",
                name="라로슈포제 시카플라스트 밤B5",
                current_stock=12,
                threshold=12,
                unit_weight=40,
                last_updated=now,
            ),
        ]
        for item in initial_items:
            self._items[item.product_id] = item

    def _get_item(self, product_id: str) -> InventoryItem:
        item = self._items.get(product_id)
        if not item:
            raise ValueError(f"상품을 찾을 수 없습니다: {product_id}")
        return item

    def get_status(self) -> InventoryStatusResponse:
        items = list(self._items.values())
        low_stock = [item for item in items if item.current_stock <= item.threshold]
        return InventoryStatusResponse(
            success=True,
            total_items=len(items),
            low_stock_count=len(low_stock),
            items=items,
        )

    def get_alerts(self) -> InventoryAlertsResponse:
        alerts: List[InventoryAlert] = []
        for item in self._items.values():
            if item.current_stock <= item.threshold:
                ratio = (
                    item.current_stock / item.threshold
                    if item.threshold > 0
                    else 0
                )
                severity = "critical" if ratio <= 0.5 else "warning"
                alerts.append(
                    InventoryAlert(
                        product_id=item.product_id,
                        name=item.name,
                        current_stock=item.current_stock,
                        threshold=item.threshold,
                        severity=severity,
                    )
                )
        return InventoryAlertsResponse(success=True, alerts=alerts)

    def update_stock(
        self,
        request: InventoryUpdateRequest,
        source: str = "manual",
    ) -> InventoryUpdateResponse:
        with self._lock:
            item = self._get_item(request.product_id)
            previous = item.current_stock
            item.current_stock = request.new_stock
            item.last_updated = datetime.utcnow()
            change = item.current_stock - previous

            self._record_history(
                product=item,
                previous_stock=previous,
                new_stock=item.current_stock,
                source=source,
                note=request.reason,
            )

            return InventoryUpdateResponse(
                success=True,
                change=change,
                item=item,
            )

    def apply_sensor_measurement(
        self,
        request: InventorySensorRequest,
    ) -> InventorySensorResponse:
        with self._lock:
            item = self._get_item(request.product_id)

            if request.unit.lower() != "g":
                raise ValueError("현재는 gram 단위만 지원합니다.")

            estimated_stock = int(request.measured_weight / item.unit_weight)
            estimated_stock = max(0, estimated_stock)
            previous = item.current_stock
            item.current_stock = estimated_stock
            item.last_updated = datetime.utcnow()

            self._record_history(
                product=item,
                previous_stock=previous,
                new_stock=item.current_stock,
                source=f"sensor:{request.sensor_id}",
                note=f"측정 무게 {request.measured_weight}{request.unit}",
            )

            return InventorySensorResponse(
                success=True,
                product_id=item.product_id,
                sensor_id=request.sensor_id,
                estimated_stock=item.current_stock,
                item=item,
            )

    def get_history(
        self,
        product_id: Optional[str] = None,
        limit: int = 50,
    ) -> InventoryHistoryResponse:
        filtered = (
            [record for record in self._history if record.product_id == product_id]
            if product_id
            else list(self._history)
        )
        filtered.sort(key=lambda record: record.timestamp, reverse=True)
        return InventoryHistoryResponse(
            success=True,
            history=filtered[:limit],
        )

    def _record_history(
        self,
        product: InventoryItem,
        previous_stock: int,
        new_stock: int,
        source: str,
        note: Optional[str] = None,
    ) -> None:
        record = InventoryHistoryRecord(
            timestamp=datetime.utcnow(),
            product_id=product.product_id,
            product_name=product.name,
            previous_stock=previous_stock,
            new_stock=new_stock,
            change=new_stock - previous_stock,
            source=source,
            note=note,
        )
        self._history.append(record)


inventory_service = InventoryService()
