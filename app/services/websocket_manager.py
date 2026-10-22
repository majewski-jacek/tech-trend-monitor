import json
import logging
from typing import Any, Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time events."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts a JSON-serializable payload to all connected clients."""
        if not self.active_connections:
            return

        dead_connections: List[WebSocket] = []
        payload_str = json.dumps(message, default=str)

        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload_str)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}. Marking for removal.")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Sends a JSON-serializable message to a specific client."""
        try:
            payload_str = json.dumps(message, default=str)
            await websocket.send_text(payload_str)
        except Exception as e:
            logger.warning(f"Error sending direct message to client: {e}")
            self.disconnect(websocket)


ws_manager = ConnectionManager()
