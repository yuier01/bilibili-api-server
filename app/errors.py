"""把 SDK 的异常翻译成稳定的 HTTP 状态码 + 业务码。

路由层不写 try/except，所有上游异常在这里统一收口。
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from bilibili_api import (
    ApiException,
    ArgsException,
    CredentialNoAcTimeValueException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
    WbiRetryTimesExceedException,
)

log = logging.getLogger("app.errors")

# B 站业务码 -> (HTTP 状态码, 业务码)
STATUS_BY_UPSTREAM_CODE: dict[int, tuple[int, str]] = {
    -101: (401, "LOGIN_REQUIRED"),
    -404: (404, "NOT_FOUND"),
    -403: (502, "WBI_REJECTED"),
    -352: (503, "RISK_CONTROL"),
    -412: (503, "RISK_CONTROL"),
    -799: (429, "UPSTREAM_RATE_LIMITED"),
}

CREDENTIAL_EXCEPTIONS = (
    CredentialNoSessdataException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoAcTimeValueException,
)


class ServiceError(Exception):
    """服务自身的错误（参数、鉴权等），不来自上游。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _error_body(request: Request, code: str, message: str, **extra: object) -> dict:
    return {"code": code, "message": message, "request_id": _request_id(request), **extra}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, exc.code, exc.message),
        )

    @app.exception_handler(ApiException)
    async def _api_error(request: Request, exc: ApiException) -> JSONResponse:
        if isinstance(exc, ResponseCodeException):
            status, code = STATUS_BY_UPSTREAM_CODE.get(
                exc.code, (502, "UPSTREAM_ERROR")
            )
            log.warning(
                "upstream business error",
                extra={"request_id": _request_id(request), "upstream_code": exc.code},
            )
            headers = {"Retry-After": "60"} if status == 503 else None
            return JSONResponse(
                status_code=status,
                content=_error_body(
                    request, code, exc.msg or str(exc), upstream_code=exc.code
                ),
                headers=headers,
            )

        if isinstance(exc, NetworkException):
            log.warning(
                "upstream network error",
                extra={"request_id": _request_id(request), "upstream_code": exc.status},
            )
            return JSONResponse(
                status_code=502,
                content=_error_body(
                    request, "UPSTREAM_NETWORK", str(exc), upstream_code=exc.status
                ),
            )

        if isinstance(exc, WbiRetryTimesExceedException):
            return JSONResponse(
                status_code=503,
                content=_error_body(request, "WBI_EXHAUSTED", str(exc)),
                headers={"Retry-After": "60"},
            )

        if isinstance(exc, ArgsException):
            return JSONResponse(
                status_code=422,
                content=_error_body(request, "BAD_REQUEST", str(exc)),
            )

        if isinstance(exc, CREDENTIAL_EXCEPTIONS):
            # 服务端配置问题：这个端点需要登录态，但没配凭据
            log.error("credential missing: %s", exc, extra={"request_id": _request_id(request)})
            return JSONResponse(
                status_code=503,
                content=_error_body(request, "CREDENTIAL_MISSING", str(exc)),
            )

        log.error(
            "unhandled sdk error: %s", exc, exc_info=exc, extra={"request_id": _request_id(request)}
        )
        return JSONResponse(
            status_code=502,
            content=_error_body(request, "UPSTREAM_ERROR", str(exc)),
        )

    @app.exception_handler(asyncio.TimeoutError)
    async def _upstream_timeout(request: Request, exc: TimeoutError) -> JSONResponse:
        log.warning("upstream timeout", extra={"request_id": _request_id(request)})
        return JSONResponse(
            status_code=504,
            content=_error_body(request, "UPSTREAM_TIMEOUT", "上游请求超时"),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(request, "BAD_REQUEST", "请求参数校验失败", details=exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, "HTTP_ERROR", str(exc.detail)),
        )
