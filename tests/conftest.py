import httpx
import pytest
from bilibili_api import request_settings

from app.main import app


@pytest.fixture
async def client():
    """跑完整 lifespan（配置 SDK、建 gate），再用 ASGI 直连 app。"""
    async with app.router.lifespan_context(app):
        # 测试里禁止 SDK 自动去取 buvid，否则每次都会多打一次真实上游
        request_settings.set_enable_auto_buvid(False)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http_client:
            yield http_client


@pytest.fixture
def api_key(client):
    """临时打开鉴权，测试结束恢复。依赖 client 保证 lifespan 已执行。"""
    settings = app.state.settings
    original = settings.api_key
    settings.api_key = "test-key"
    try:
        yield "test-key"
    finally:
        settings.api_key = original
