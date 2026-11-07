"""命令行入口。

装好后可以直接：uv run bilibili-api-server --port 8000
"""

from __future__ import annotations

import argparse

from .config import get_settings
from .logging import force_utf8_stdio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bilibili-api-server",
        description="基于 bilibili-api 的 B 站只读接口服务（RPC 风格，全 POST）",
    )
    parser.add_argument("--host", help="监听地址，默认取 BILI_HOST（127.0.0.1）")
    parser.add_argument("--port", type=int, help="监听端口，默认取 BILI_PORT（8000）")
    parser.add_argument(
        "--reload", action="store_true", help="开发模式：改代码自动重启"
    )
    parser.add_argument("--log-level", help="uvicorn 日志级别，默认取 BILI_LOG_LEVEL")
    return parser


def main(argv: list[str] | None = None) -> None:
    force_utf8_stdio()
    args = build_parser().parse_args(argv)
    settings = get_settings()

    # 延迟导入：--help 不用把整个 app 和 SDK 都加载起来
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
        log_level=(args.log_level or settings.log_level).lower(),
    )
