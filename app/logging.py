"""JSON 行日志：方便 grep，也方便以后接采集。"""

from __future__ import annotations

import json
import logging
import sys

_EXTRA_FIELDS = (
    "request_id",
    "method",
    "path",
    "status",
    "elapsed_ms",
    "upstream_code",
    "client",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    # Windows 控制台默认 GBK，日志里的中文会乱码；统一成 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # SDK 默认会往 stderr 打请求日志，这里让它们跟应用日志走同一个格式
    logging.getLogger("bilibili-api-request").setLevel(logging.WARNING)
    # 每次上游请求都打一行太吵，access 日志里已经有耗时了
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
