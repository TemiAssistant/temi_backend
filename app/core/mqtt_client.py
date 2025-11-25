import json
import logging
import os
from typing import Optional

import paho.mqtt.client as mqtt

from app.models.inventory import InventorySensorRequest
from app.services.inventory_service import inventory_service
from app.core.firebase import firebase_service


logger = logging.getLogger(__name__)


class MQTTInventoryBridge:
    """MQTT <-> 재고 시스템 브리지 (로드셀 → Firebase/Inventory)"""

    def __init__(self) -> None:
        self.enabled = os.getenv("MQTT_ENABLED", "true").lower() not in {"0", "false", "no"}
        self.host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self.port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self.username = os.getenv("MQTT_USERNAME")
        self.password = os.getenv("MQTT_PASSWORD")
        self.topic = os.getenv("MQTT_SENSOR_TOPIC", "inventory/sensors/#")
        self.keep_alive = int(os.getenv("MQTT_KEEPALIVE", "60"))

        self._client: Optional[mqtt.Client] = None
        self._connected = False

    def start(self) -> None:
        if not self.enabled:
            logger.info("MQTT bridge disabled via environment variable.")
            return

        if self._client:
            logger.debug("MQTT bridge already running.")
            return

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.on_disconnect = self._on_disconnect

            if self.username and self.password:
                client.username_pw_set(self.username, self.password)

            client.connect(self.host, self.port, self.keep_alive)
            client.loop_start()
            self._client = client
            logger.info("MQTT bridge connecting to %s:%s topic=%s", self.host, self.port, self.topic)
        except Exception as exc:
            logger.exception("Failed to start MQTT bridge: %s", exc)
            self._client = None

    def stop(self) -> None:
        if not self._client:
            return
        logger.info("Stopping MQTT bridge.")
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None
        self._connected = False

    # MQTT callbacks -----------------------------------------------------

    def _on_connect(self, client: mqtt.Client, _userdata, _flags, reason_code, _properties=None):
        if reason_code.is_failure:
            logger.error("MQTT connection failed: %s", reason_code)
            return
        self._connected = True
        client.subscribe(self.topic)
        logger.info("MQTT connected. Subscribed to %s", self.topic)

    def _on_disconnect(self, _client: mqtt.Client, _userdata, reason_code, _properties=None):
        self._connected = False
        if reason_code != 0:
            logger.warning("MQTT disconnected unexpectedly: %s", reason_code)
        else:
            logger.info("MQTT disconnected.")

    def _on_message(self, _client: mqtt.Client, _userdata, message: mqtt.MQTTMessage):
        try:
            payload = message.payload.decode("utf-8")
            data = json.loads(payload)
            self._fill_ids_from_topic(data, message.topic)
            request = InventorySensorRequest(**data)
        except Exception as exc:
            logger.warning("Invalid MQTT payload on %s: %s", message.topic, exc)
            return

        try:
            response = inventory_service.apply_sensor_measurement(request)
            self._sync_to_firebase(response)
            logger.info(
                "MQTT sensor update applied product=%s sensor=%s stock=%s",
                response.product_id,
                request.sensor_id,
                response.estimated_stock,
            )
        except Exception as exc:
            logger.exception("Failed to apply sensor measurement: %s", exc)

    def _fill_ids_from_topic(self, data: dict, topic: str) -> None:
        """토픽 구조에서 product_id/sensor_id 추론 (inventory/sensors/<product>/<sensor>)."""
        parts = topic.split("/")
        if "product_id" not in data and len(parts) >= 3:
            data["product_id"] = parts[-2]
        if "sensor_id" not in data and len(parts) >= 2:
            data["sensor_id"] = parts[-1]

    def _sync_to_firebase(self, response):
        item = response.item
        payload = {
            "product_id": item.product_id,
            "name": item.name,
            "current_stock": item.current_stock,
            "threshold": item.threshold,
            "unit_weight": item.unit_weight,
            "last_updated": item.last_updated.isoformat(),
            "source": "mqtt",
        }

        try:
            if firebase_service.firestore_db:
                firebase_service.firestore_db.collection("inventory").document(item.product_id).set(payload, merge=True)
            if firebase_service.realtime_db:
                firebase_service.realtime_db.child("inventory").child(item.product_id).update(payload)
        except Exception as exc:
            logger.warning("Failed to sync inventory to Firebase: %s", exc)


mqtt_bridge = MQTTInventoryBridge()
