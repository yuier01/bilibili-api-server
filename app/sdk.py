"""SDK 初始化。

`request_settings` 是进程级全局单例，所以只在启动时配置一次，
运行中不要再改（见 PLAN.md §6.5）。
"""

from __future__ import annotations

import logging

from bilibili_api import (
    get_client,
    get_registered_clients,
    get_selected_client,
    request_settings,
    select_client,
)

from .config import Settings

log = logging.getLogger("app.sdk")


def configure_sdk(settings: Settings) -> None:
    request_settings.set_timeout(settings.upstream_timeout)
    request_settings.set_enable_auto_buvid(True)
    request_settings.set_wbi_retry_times(3)

    if settings.proxy:
        request_settings.set_proxy(settings.proxy)

    if settings.client != "httpx":
        if settings.client in get_registered_clients():
            select_client(settings.client)
        else:
            log.warning(
                "client %r 未注册（可能没装对应库），继续使用 httpx", settings.client
            )

    name, _ = get_selected_client()
    log.info("sdk ready: client=%s timeout=%ss", name, settings.upstream_timeout)


async def shutdown_sdk() -> None:
    try:
        client = get_client()
    except Exception:  # noqa: BLE001 - 没装第三方请求库时 get_client 会抛异常
        return
    await client.close()
