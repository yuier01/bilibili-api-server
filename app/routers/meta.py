"""元信息 / 健康检查。"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from bilibili_api import BILIBILI_API_VERSION, get_selected_client

from ..auth import require_api_key

router = APIRouter(tags=["meta"])


@router.get("/healthz", summary="存活检查（不需要鉴权，给容器 healthcheck 用）")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/meta", dependencies=[Depends(require_api_key)], summary="服务与 SDK 状态")
async def meta(request: Request) -> dict:
    app = request.app
    client_name, _ = get_selected_client()
    settings = app.state.settings
    return {
        "sdk_version": BILIBILI_API_VERSION,
        "client": client_name,
        "auth_enabled": bool(settings.api_key),
        "logged_in": False,
        "upstream_concurrency": settings.upstream_concurrency,
        "inflight_upstream": app.state.gate.inflight,
        "uptime_seconds": round(time.time() - app.state.started_at, 1),
    }
