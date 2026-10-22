import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.datetime_utils import format_utc_iso, utc_now
from app.services.websocket_manager import ws_manager

logger = logging.getLogger("websocket_api")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time bidirectional WebSocket connection for live dashboard telemetry.
    Streams new article notifications, sentiment updates, and sync events.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial confirmation message upon successful connection
        await websocket.send_text(
            json.dumps({
                "type": "CONNECTED",
                "message": "Connected to TechTrend Live Telemetry Stream",
                "timestamp": format_utc_iso(utc_now())
            })
        )

        while True:
            # Keep connection alive and process any client-side queries
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                msg_type = data.get("type", "").lower()
                if msg_type == "ping":
                    await websocket.send_text(
                        json.dumps({
                            "type": "PONG",
                            "timestamp": format_utc_iso(utc_now())
                        })
                    )
            except Exception:
                # Echo or ignore non-JSON messages
                pass

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"Unexpected WebSocket error: {e}")
        ws_manager.disconnect(websocket)
