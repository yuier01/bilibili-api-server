"""链接解析：从分享文案 / b23.tv 短链 / B 站长链 / 裸 ID 里提取资源标识。

纯函数，不发请求；短链跳转由 router 层负责（需要走 Gate）。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# 分享文案里抠 URL：遇到空白、中文标点或引号就截断
URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'“”‘’，。！？、；：）】]+")
SHORT_URL_IN_TEXT = re.compile(r"\bb23\.tv/[0-9A-Za-z]+", re.IGNORECASE)

BARE_ID = re.compile(r"(?i)^(BV[0-9A-Za-z]{10}|av\d+|ep\d+|ss\d+|cv\d+)$")

BVID_IN_PATH = re.compile(r"/video/(BV[0-9A-Za-z]{10})", re.IGNORECASE)
AID_IN_PATH = re.compile(r"/video/av(\d+)", re.IGNORECASE)
EP_IN_PATH = re.compile(r"/bangumi/play/ep(\d+)", re.IGNORECASE)
SS_IN_PATH = re.compile(r"/bangumi/play/ss(\d+)", re.IGNORECASE)
CV_IN_PATH = re.compile(r"/read/cv(\d+)", re.IGNORECASE)
AUID_IN_PATH = re.compile(r"/audio/au(\d+)", re.IGNORECASE)
OPUS_IN_PATH = re.compile(r"/(?:opus|dynamic)/(\d+)")
ROOM_IN_PATH = re.compile(r"^/(\d+)")
UID_IN_PATH = re.compile(r"^/(\d+)")

SHORT_HOSTS = {"b23.tv"}


def is_short_url(url: str) -> bool:
    return urlparse(url).netloc.lower() in SHORT_HOSTS


def normalize_input(text: str) -> tuple[str | None, str | None]:
    """把用户输入拆成 (url, bare_id) 之一。

    - 整段分享文案 -> 抠出第一个 http(s) URL
    - 只有 `b23.tv/xxx` 没有协议头 -> 补 https://
    - 裸 BV/av/ep/ss/cv -> 原样作为 bare_id
    """
    text = text.strip()

    match = URL_IN_TEXT.search(text)
    if match:
        return match.group(0).rstrip(".,;:!?)]}"), None

    match = SHORT_URL_IN_TEXT.search(text)
    if match:
        return "https://" + match.group(0), None

    if BARE_ID.match(text):
        return None, text

    return None, None


def _video(bvid: str | None = None, aid: int | None = None) -> dict[str, Any]:
    resource: dict[str, Any] = {"type": "video"}
    if bvid:
        resource.update(bvid=bvid, url=f"https://www.bilibili.com/video/{bvid}")
    else:
        resource.update(aid=aid, url=f"https://www.bilibili.com/video/av{aid}")
    return resource


def parse_bare_id(value: str) -> dict[str, Any] | None:
    if value[:2].upper() == "BV":
        # BV 前缀必须大写，后半段保持原样
        return _video(bvid="BV" + value[2:])
    if value[:2].lower() == "av":
        return _video(aid=int(value[2:]))
    if value[:2].lower() == "ep":
        return {
            "type": "bangumi",
            "ep_id": int(value[2:]),
            "url": f"https://www.bilibili.com/bangumi/play/ep{int(value[2:])}",
        }
    if value[:2].lower() == "ss":
        return {
            "type": "bangumi",
            "season_id": int(value[2:]),
            "url": f"https://www.bilibili.com/bangumi/play/ss{int(value[2:])}",
        }
    if value[:2].lower() == "cv":
        return {
            "type": "article",
            "cv_id": int(value[2:]),
            "url": f"https://www.bilibili.com/read/cv{int(value[2:])}",
        }
    return None


def parse_bilibili_url(url: str) -> dict[str, Any] | None:
    """解析 B 站长链（已跳转后的地址）。不认识的站点/路径返回 None。"""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    path = parsed.path

    if not (host == "bilibili.com" or host.endswith(".bilibili.com")):
        return None

    if host == "t.bilibili.com":
        if match := UID_IN_PATH.match(path):
            dynamic_id = int(match[1])
            return {
                "type": "dynamic",
                "dynamic_id": dynamic_id,
                "url": f"https://t.bilibili.com/{dynamic_id}",
            }
        return None

    if host.startswith("live."):
        if match := ROOM_IN_PATH.match(path):
            room_id = int(match[1])
            return {
                "type": "live",
                "room_id": room_id,
                "url": f"https://live.bilibili.com/{room_id}",
            }
        return None

    if host.startswith("space."):
        if match := UID_IN_PATH.match(path):
            uid = int(match[1])
            return {
                "type": "user",
                "uid": uid,
                "url": f"https://space.bilibili.com/{uid}",
            }
        return None

    if match := BVID_IN_PATH.search(path):
        return _video(bvid="BV" + match[1][2:])
    if match := AID_IN_PATH.search(path):
        return _video(aid=int(match[1]))
    if match := EP_IN_PATH.search(path):
        ep_id = int(match[1])
        return {
            "type": "bangumi",
            "ep_id": ep_id,
            "url": f"https://www.bilibili.com/bangumi/play/ep{ep_id}",
        }
    if match := SS_IN_PATH.search(path):
        season_id = int(match[1])
        return {
            "type": "bangumi",
            "season_id": season_id,
            "url": f"https://www.bilibili.com/bangumi/play/ss{season_id}",
        }
    if match := CV_IN_PATH.search(path):
        cv_id = int(match[1])
        return {
            "type": "article",
            "cv_id": cv_id,
            "url": f"https://www.bilibili.com/read/cv{cv_id}",
        }
    if match := AUID_IN_PATH.search(path):
        auid = int(match[1])
        return {
            "type": "audio",
            "auid": auid,
            "url": f"https://www.bilibili.com/audio/au{auid}",
        }
    if match := OPUS_IN_PATH.search(path):
        dynamic_id = int(match[1])
        return {
            "type": "dynamic",
            "dynamic_id": dynamic_id,
            "url": f"https://t.bilibili.com/{dynamic_id}",
        }

    return None
