"""统一响应包。"""

from __future__ import annotations

from typing import Any

from fastapi import Request


def envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ok",
        "data": data,
        "request_id": getattr(request.state, "request_id", ""),
    }
