import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_websocket_connection_and_telemetry(client):
    """Verifies that WebSocket clients can connect, receive welcome telemetry, and exchange ping/pong."""
    with client.websocket_connect("/ws") as websocket:
        try:
            # Receive initial welcome message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "CONNECTED"
            assert "Live Telemetry" in message["message"]

            # Send ping
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            resp_msg = json.loads(response)
            assert resp_msg["type"] == "PONG"
            assert "timestamp" in resp_msg
        finally:
            # Explicitly close websocket connection before exit
            websocket.close()

    # Allow Windows Proactor event loop to cleanly process transport closing callbacks
    await asyncio.sleep(0.01)
