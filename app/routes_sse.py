import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.database import SessionLocal
from app.models import Lead

logger = logging.getLogger("crm.sse")

router = APIRouter(prefix="/api/sse", tags=["sse"])

MSK = timezone(timedelta(hours=3))

CLIENTS = []


@router.get("/events")
async def sse_events(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    CLIENTS.append(queue)
    logger.info(f"SSE client connected, total: {len(CLIENTS)}")

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            if queue in CLIENTS:
                CLIENTS.remove(queue)
            logger.info(f"SSE client disconnected, total: {len(CLIENTS)}")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def broadcast(event: dict):
    for q in CLIENTS[:]:
        try:
            await q.put(event)
        except Exception:
            pass


def notify_new_lead(lead_id: int, name: str, phone: str, service_type: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast({
            "type": "new_lead",
            "lead_id": lead_id,
            "name": name,
            "phone": phone,
            "service_type": service_type,
        }))
    except RuntimeError:
        pass
