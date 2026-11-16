import httpx
import pytest
import respx

SHARE_LOCATION = (
    "https://www.bilibili.com/video/BV1Qc411h7Ys"
    "?buvid=XU08&from_spmid=united.player-video-detail&p=1"
    "&share_source=QQ&unique_k=me5NG2c&up_id=90942983"
)


@respx.mock
async def test_short_link_7char(client):
    respx.head("https://b23.tv/me5NG2c").mock(
        return_value=httpx.Response(302, headers={"location": SHARE_LOCATION})
    )
    response = await client.post("/v1/common/parse_url", json={"url": "https://b23.tv/me5NG2c"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["type"] == "video"
    assert data["bvid"] == "BV1Qc411h7Ys"
    assert data["url"] == "https://www.bilibili.com/video/BV1Qc411h7Ys"


@respx.mock
async def test_short_link_without_scheme(client):
    respx.head("https://b23.tv/abc1234").mock(
        return_value=httpx.Response(302, headers={"location": SHARE_LOCATION})
    )
    response = await client.post("/v1/common/parse_url", json={"url": "b23.tv/abc1234"})

    assert response.status_code == 200
    assert response.json()["data"]["bvid"] == "BV1Qc411h7Ys"


@respx.mock
async def test_share_text_extracts_url(client):
    respx.head("https://b23.tv/me5NG2c").mock(
        return_value=httpx.Response(302, headers={"location": SHARE_LOCATION})
    )
    response = await client.post(
        "/v1/common/parse_url",
        json={"url": "【官方 MV】Never Gonna Give You Up https://b23.tv/me5NG2c 快看"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["bvid"] == "BV1Qc411h7Ys"


@respx.mock
async def test_expired_short_link(client):
    respx.head("https://b23.tv/dead000").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"})
    )
    response = await client.post("/v1/common/parse_url", json={"url": "https://b23.tv/dead000"})

    assert response.status_code == 422
    assert response.json()["code"] == "UNPARSEABLE_URL"


async def test_long_video_url(client):
    response = await client.post(
        "/v1/common/parse_url",
        json={"url": "https://www.bilibili.com/video/BV1GJ411x7h7?p=1&spm_id_from=333.999"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["type"] == "video"
    assert data["bvid"] == "BV1GJ411x7h7"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BV1GJ411x7h7", {"type": "video", "bvid": "BV1GJ411x7h7"}),
        ("av80433022", {"type": "video", "aid": 80433022}),
        ("https://www.bilibili.com/video/av80433022", {"type": "video", "aid": 80433022}),
        ("ep123456", {"type": "bangumi", "ep_id": 123456}),
        ("https://www.bilibili.com/bangumi/play/ss28747", {"type": "bangumi", "season_id": 28747}),
        ("https://live.bilibili.com/22637261", {"type": "live", "room_id": 22637261}),
        ("https://space.bilibili.com/2", {"type": "user", "uid": 2}),
        ("https://www.bilibili.com/read/cv123456", {"type": "article", "cv_id": 123456}),
        ("https://t.bilibili.com/1234567890", {"type": "dynamic", "dynamic_id": 1234567890}),
    ],
)
async def test_various_inputs(client, text, expected):
    response = await client.post("/v1/common/parse_url", json={"url": text})

    assert response.status_code == 200
    data = response.json()["data"]
    for key, value in expected.items():
        assert data[key] == value, f"{key}: {data.get(key)} != {value}"


@pytest.mark.parametrize(
    "text",
    [
        "https://www.bilibili.com/foo/bar",
        "https://example.com/video/BV1GJ411x7h7",
        "随便一段没有链接的话",
    ],
)
async def test_unparseable(client, text):
    response = await client.post("/v1/common/parse_url", json={"url": text})

    assert response.status_code == 422
    assert response.json()["code"] in {"UNPARSEABLE_URL", "INVALID_URL"}


async def test_empty_input(client):
    response = await client.post("/v1/common/parse_url", json={"url": ""})

    assert response.status_code == 422
    assert response.json()["code"] == "BAD_REQUEST"


@respx.mock
async def test_parse_url_requires_api_key(client, api_key):
    respx.head("https://b23.tv/me5NG2c").mock(
        return_value=httpx.Response(302, headers={"location": SHARE_LOCATION})
    )

    unauthorized = await client.post("/v1/common/parse_url", json={"url": "https://b23.tv/me5NG2c"})
    assert unauthorized.status_code == 401

    authorized = await client.post(
        "/v1/common/parse_url",
        json={"url": "https://b23.tv/me5NG2c"},
        headers={"X-API-Key": api_key},
    )
    assert authorized.status_code == 200
