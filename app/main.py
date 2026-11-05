"""应用装配。"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .errors import install_error_handlers
from .gate import Gate
from .logging import setup_logging
from .middleware import RequestContextMiddleware
from .routers import meta, video
from .sdk import configure_sdk, shutdown_sdk

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    app.state.settings = settings
    app.state.started_at = time.time()
    # 比 SDK 自己的超时多一点余量，让 SDK 先超时、拿到更准确的错误
    app.state.gate = Gate(
        concurrency=settings.upstream_concurrency,
        timeout=settings.upstream_timeout + 2,
    )

    configure_sdk(settings)

    if not settings.api_key:
        log.warning("BILI_API_KEY 为空，鉴权已关闭（仅建议本机使用）")

    log.info("service started")
    try:
        yield
    finally:
        await shutdown_sdk()
        log.info("service stopped")


app = FastAPI(
    title="bilibili-api-server",
    version="0.1.0",
    description="基于 bilibili-api 的第三方 B 站只读接口服务（dev 版）",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
install_error_handlers(app)

app.include_router(meta.router)
app.include_router(video.router)
