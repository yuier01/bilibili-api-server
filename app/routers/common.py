"""通用方法：链接/分享文案解析。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from bilibili_api import get_client

from ..auth import require_api_key
from ..errors import ServiceError
from ..links import is_short_url, normalize_input, parse_bare_id, parse_bilibili_url
from ..schemas import envelope

router = APIRouter(prefix="/v1", tags=["common"], dependencies=[Depends(require_api_key)])


class ParseUrlRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=1,
        description="分享文案 / b23.tv 短链 / B 站长链 / 裸 BV·av·ep·ss·cv 号",
        json_schema_extra={"examples": ["https://b23.tv/me5NG2c"]},
    )


async def _resolve_short(url: str, request: Request) -> str:
    """HEAD 且不跟随跳转，只读 Location。

    不用 `get_real_url()`：它默认 allow_redirects=True，会跟到 bilibili.com，
    每条短链都白发一次请求，还会吃到 412 风控页。
    """
    client = get_client()
    response = await request.app.state.gate.run(
        lambda: client.request(method="HEAD", url=url, allow_redirects=False)
    )
    location = response.headers.get("location") or response.headers.get("Location")
    if not location:
        raise ServiceError(
            422,
            "UNPARSEABLE_URL",
            "短链没有跳转目标，可能已过期，或不是 B 站分享链接",
        )
    return location


@router.post(
    "/common/parse_url",
    summary="把分享链接解析成资源标识",
    description=(
        "支持：分享文案、b23.tv 短链（含 7 位随机码）、B 站长链、裸 BV/av/ep/ss/cv 号。"
        "返回 type 与对应 id，便于后续调用其它方法。"
    ),
)
async def parse_url(payload: ParseUrlRequest, request: Request) -> dict[str, Any]:
    url, bare_id = normalize_input(payload.url)

    if bare_id:
        resource = parse_bare_id(bare_id)
        if resource is None:
            raise ServiceError(422, "INVALID_URL", f"无法识别的 ID：{bare_id}")
        return envelope(request, resource)

    if url is None:
        raise ServiceError(422, "INVALID_URL", "没有找到可解析的链接或 ID")

    if is_short_url(url):
        url = await _resolve_short(url, request)

    resource = parse_bilibili_url(url)
    if resource is None:
        raise ServiceError(422, "UNPARSEABLE_URL", f"不支持的链接：{url}")

    return envelope(request, resource)
