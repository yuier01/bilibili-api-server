"""X-API-Key 鉴权。

BILI_API_KEY 为空时直接放行（本机开发用）；设置后所有 /v1 路由都要带
`X-API-Key`。比较用 constant-time，避免时序侧信道。
"""

from __future__ import annotations

import secrets

from fastapi import Header, Request

from .errors import ServiceError


async def require_api_key(
    request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> None:
    expected = request.app.state.settings.api_key
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise ServiceError(401, "UNAUTHORIZED", "缺少或错误的 X-API-Key")
