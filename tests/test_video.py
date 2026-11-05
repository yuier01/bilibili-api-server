import httpx
import pytest
import respx

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"

VIEW_DATA = {
    "bvid": "BV1GJ411x7h7",
    "aid": 80433022,
    "title": "【官方 MV】Never Gonna Give You Up - Rick Astley",
    "desc": "经典永流传",
    "pic": "http://i0.hdslb.com/bfs/archive/cover.jpg",
    "duration": 213,
    "pubdate": 1576500000,
    "ctime": 1576500000,
    "tid": 21,
    "tname": "日常",
    "copyright": 1,
    "state": 0,
    "owner": {"mid": 946974, "name": "索尼音乐中国", "face": "http://i0.hdslb.com/bfs/face/a.jpg"},
    "stat": {
        "view": 108042966,
        "danmaku": 12345,
        "reply": 6789,
        "favorite": 111111,
        "coin": 1291104,
        "share": 222222,
        "like": 2971293,
        "his_rank": 0,
        "now_rank": 0,
    },
    "pages": [
        {
            "cid": 137649199,
            "page": 1,
            "part": "MV",
            "duration": 213,
            "dimension": {"width": 1920, "height": 1080, "rotate": 0},
        }
    ],
}


def mock_view(payload: dict | None = None, code: int = 0) -> None:
    body = (
        {"code": 0, "message": "0", "ttl": 1, "data": payload or VIEW_DATA}
        if code == 0
        else {"code": code, "message": "上游错误", "ttl": 1}
    )
    respx.get(VIEW_URL).mock(return_value=httpx.Response(200, json=body))


@respx.mock
async def test_video_info_ok(client):
    mock_view()
    response = await client.post("/v1/video/get_info", json={"bvid": "BV1GJ411x7h7"})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]

    data = body["data"]
    assert data["bvid"] == "BV1GJ411x7h7"
    assert data["title"].startswith("【官方 MV】")
    assert data["owner"]["name"] == "索尼音乐中国"
    assert data["stat"]["view"] == 108042966
    assert data["pages"][0]["cid"] == 137649199
    # 封面/头像统一升 https，尺寸从 dimension 拍平
    assert data["cover"] == "https://i0.hdslb.com/bfs/archive/cover.jpg"
    assert data["owner"]["face"].startswith("https://")
    assert data["pages"][0]["width"] == 1920


@respx.mock
async def test_raw_returns_upstream_shape(client):
    mock_view()
    response = await client.post(
        "/v1/video/get_info", json={"bvid": "BV1GJ411x7h7", "raw": True}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pic"].endswith("cover.jpg")  # 未裁剪，保留上游字段名
    assert data["stat"]["coin"] == 1291104


async def test_invalid_bvid(client):
    response = await client.post("/v1/video/get_info", json={"bvid": "BV123"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_BVID"
    assert body["request_id"]


async def test_missing_bvid_is_validation_error(client):
    response = await client.post("/v1/video/get_info", json={})

    assert response.status_code == 422
    assert response.json()["code"] == "BAD_REQUEST"


async def test_get_method_not_allowed(client):
    response = await client.get("/v1/video/get_info")

    assert response.status_code == 405
    assert response.json()["code"] == "HTTP_ERROR"


@respx.mock
async def test_upstream_not_found(client):
    mock_view(code=-404)
    response = await client.post("/v1/video/get_info", json={"bvid": "BV1GJ411x7h7"})

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["upstream_code"] == -404


@respx.mock
async def test_risk_control_maps_to_503(client):
    mock_view(code=-412)
    response = await client.post("/v1/video/get_info", json={"bvid": "BV1GJ411x7h7"})

    assert response.status_code == 503
    assert response.json()["code"] == "RISK_CONTROL"
    assert response.headers["Retry-After"] == "60"


@respx.mock
async def test_api_key_required(client, api_key):
    mock_view()

    unauthorized = await client.post("/v1/video/get_info", json={"bvid": "BV1GJ411x7h7"})
    assert unauthorized.status_code == 401
    assert unauthorized.json()["code"] == "UNAUTHORIZED"

    authorized = await client.post(
        "/v1/video/get_info",
        json={"bvid": "BV1GJ411x7h7"},
        headers={"X-API-Key": api_key},
    )
    assert authorized.status_code == 200


async def test_healthz_is_open(client):
    response = await client.post("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_meta(client):
    response = await client.post("/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["sdk_version"] == "17.4.1"
    assert body["client"] == "httpx"
