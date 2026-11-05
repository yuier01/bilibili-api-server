"""视频相关端点（RPC 风格：路径 = 方法，参数走 JSON body）。"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from bilibili_api import video

from ..auth import require_api_key
from ..errors import ServiceError
from ..schemas import envelope

router = APIRouter(prefix="/v1", tags=["video"], dependencies=[Depends(require_api_key)])

BVID_PATTERN = re.compile(r"^BV[0-9A-Za-z]{10}$")

STAT_FIELDS = (
    "view",
    "danmaku",
    "reply",
    "favorite",
    "coin",
    "share",
    "like",
    "his_rank",
    "now_rank",
)

PAGE_FIELDS = ("cid", "page", "part", "duration")


class GetVideoInfoRequest(BaseModel):
    bvid: str = Field(
        ...,
        description="BV 号，形如 BV1GJ411x7h7",
        json_schema_extra={"examples": ["BV1GJ411x7h7"]},
    )
    raw: bool = Field(False, description="true 时返回 B 站原始结构（不裁剪）")


def _https(url: str | None) -> str | None:
    """B 站封面/头像常返回 http，机器人侧容易被当混流内容拦掉，统一升到 https。"""
    if url and url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def _trim(info: dict[str, Any]) -> dict[str, Any]:
    """只保留稳定字段，避免把上游几百个字段原样甩给机器人。"""
    owner = info.get("owner") or {}
    stat = info.get("stat") or {}
    pages = []
    for page in info.get("pages") or []:
        item = {field: page.get(field) for field in PAGE_FIELDS}
        dimension = page.get("dimension") or {}
        item["width"] = dimension.get("width")
        item["height"] = dimension.get("height")
        pages.append(item)

    return {
        "bvid": info.get("bvid"),
        "aid": info.get("aid"),
        "title": info.get("title"),
        "desc": info.get("desc"),
        "cover": _https(info.get("pic")),
        "duration": info.get("duration"),
        "pubdate": info.get("pubdate"),
        "ctime": info.get("ctime"),
        "tid": info.get("tid"),
        "tname": info.get("tname"),
        "copyright": info.get("copyright"),
        "state": info.get("state"),
        "owner": {
            "mid": owner.get("mid"),
            "name": owner.get("name"),
            "face": _https(owner.get("face")),
        },
        "stat": {field: stat.get(field) for field in STAT_FIELDS},
        "pages": pages,
    }


@router.post(
    "/video/get_info",
    summary="按 BV 号查询视频信息",
    description=(
        "参数全部走 JSON body。默认返回裁剪后的稳定字段，`raw=true` 返回上游原始结构。"
    ),
)
async def get_video_info(payload: GetVideoInfoRequest, request: Request) -> dict[str, Any]:
    if not BVID_PATTERN.match(payload.bvid):
        raise ServiceError(422, "INVALID_BVID", "BV 号格式不合法，应形如 BV1GJ411x7h7")

    video_obj = video.Video(bvid=payload.bvid)
    data = await request.app.state.gate.run(video_obj.get_info)
    return envelope(request, data if payload.raw else _trim(data))
