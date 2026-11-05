# bilibili-api-server (dev)

基于 [`bilibili-api`](../../bilibili-api)（17.4.1）的最小可用 B 站只读接口服务。
当前只交付一个端点：**按 BV 号查询视频信息**，匿名即可用，不需要任何 cookie。

设计细节见上级目录的 [PLAN.md](../PLAN.md)。

## 快速开始

要求：Python ≥ 3.11、[uv](https://docs.astral.sh/uv/)。

```powershell
cd bilibili-api-server\dev
uv sync                      # 建 .venv，并以 editable 方式装本地 SDK（../../bilibili-api）
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/docs> 看自动生成的接口文档。

```powershell
curl "http://127.0.0.1:8000/v1/video/BV1GJ411x7h7"
```

> 如果不用 uv：`python -m venv .venv` → 激活 → `pip install -e ../../bilibili-api` →
> `pip install fastapi "uvicorn[standard]" pydantic-settings httpx`。
> 注意 **`httpx` 必须显式安装**：它不在 SDK 的 `pyproject` 依赖里（只在 `requirements.txt`），
> 缺了会在首次请求时报 `ArgsException: 尚未安装第三方请求库`。

## 配置

全部通过环境变量（`BILI_` 前缀）或同目录 `.env` 覆盖，参考 `.env.example`。

| 变量 | 默认 | 说明 |
|---|---|---|
| `BILI_API_KEY` | 空 | 空 = 关闭鉴权；设置后 `/v1/*` 需带 `X-API-Key` |
| `BILI_HOST` / `BILI_PORT` | `127.0.0.1` / `8000` | 默认只听本机 |
| `BILI_UPSTREAM_TIMEOUT` | `10` | 单次上游超时（秒） |
| `BILI_UPSTREAM_CONCURRENCY` | `6` | 同时打到 B 站的请求上限 |
| `BILI_CLIENT` | `httpx` | 可切 `curl_cffi`（需先装该库） |
| `BILI_PROXY` | 空 | 全局代理 |
| `BILI_LOG_LEVEL` | `INFO` | JSON 行日志级别 |

## 接口

### `GET /v1/video/{bvid}`

| 参数 | 位置 | 说明 |
|---|---|---|
| `bvid` | path | 形如 `BV1GJ411x7h7`（`BV` + 10 位字母数字） |
| `raw` | query | `true` 时返回 B 站原始结构（45 个字段），否则返回裁剪后的稳定字段 |

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "bvid": "BV1GJ411x7h7",
    "aid": 80433022,
    "title": "【官方 MV】Never Gonna Give You Up - Rick Astley",
    "desc": "-",
    "cover": "https://i1.hdslb.com/bfs/archive/5242750857121e05146d5d5b13a47a2a6dd36e98.jpg",
    "duration": 213,
    "pubdate": 1577835803,
    "ctime": 1577835803,
    "tid": 193,
    "tname": "",
    "copyright": 1,
    "state": 0,
    "owner": { "mid": 486906719, "name": "索尼音乐中国", "face": "https://..." },
    "stat": {
      "view": 108043137,
      "danmaku": 151671,
      "reply": 239924,
      "favorite": 1563438,
      "coin": 1291104,
      "share": 505573,
      "like": 2971295,
      "his_rank": 0,
      "now_rank": 0
    },
    "pages": [
      { "cid": 137649199, "page": 1, "part": "...", "duration": 213, "width": 1920, "height": 1080 }
    ]
  },
  "request_id": "b7ecb4ae3cd6"
}
```

几点约定：

- `cover` / `owner.face` 统一转成 `https`（B 站常返回 `http`，机器人侧容易被拦）。
- 只保留稳定字段；需要上游全量数据用 `?raw=true`，避免上游加字段就破坏调用方。
- 每次响应带 `X-Request-ID` 与 `X-Elapsed-MS` 头，和响应体里的 `request_id` 一致，便于对日志。

### 其它

- `GET /healthz` — 存活检查，不需要鉴权（给容器 healthcheck 用）。
- `GET /v1/meta` — SDK 版本、当前 client、鉴权开关、在途上游请求数、运行时长。

## 错误约定

HTTP 状态码 + 稳定业务码，调用方只需判断这两层：

| 业务码 | HTTP | 含义 |
|---|---|---|
| `INVALID_BVID` | 422 | BV 号格式不对（本地校验，不打上游） |
| `UNAUTHORIZED` | 401 | 缺少/错误的 `X-API-Key` |
| `NOT_FOUND` | 404 | 上游 `-404`（视频不存在/已删除） |
| `WBI_REJECTED` | 502 | 上游 `-403`，wbi 重试后仍失败 |
| `RISK_CONTROL` | 503 | 上游 `-352` / `-412`（风控），带 `Retry-After: 60` |
| `UPSTREAM_RATE_LIMITED` | 429 | 上游 `-799`（请求过于频繁） |
| `LOGIN_REQUIRED` | 401 | 上游 `-101`（当前端点无需登录，预留给后续登录态端点） |
| `UPSTREAM_NETWORK` | 502 | 网络层失败 |
| `UPSTREAM_TIMEOUT` | 504 | 超过 `BILI_UPSTREAM_TIMEOUT` |
| `CREDENTIAL_MISSING` | 503 | 端点需要登录态但服务未配置凭据 |
| `HTTP_ERROR` | 4xx/5xx | 路由不存在等框架级错误 |

```json
{ "code": "NOT_FOUND", "message": "啥都木有", "request_id": "4bd4d524f4d5", "upstream_code": -404 }
```

## 测试

```powershell
uv run pytest -q
```

用 `respx` 把上游完全 mock 掉，测试不碰真实 B 站；覆盖成功、`raw`、非法 BV、`-404`、`-412`、鉴权、健康检查。

## 目录结构

```
dev/
├── app/
│   ├── main.py           # 装配、lifespan
│   ├── config.py         # pydantic-settings
│   ├── auth.py           # X-API-Key（constant-time 比较）
│   ├── errors.py         # SDK 异常 -> HTTP 状态码/业务码
│   ├── gate.py           # 上游并发上限 + 超时
│   ├── logging.py        # JSON 行日志（Windows 下强制 UTF-8）
│   ├── middleware.py     # request_id / 耗时 / 访问日志
│   ├── sdk.py            # SDK 全局设置（一次性）
│   ├── schemas.py        # 响应包
│   └── routers/
│       ├── meta.py       # /healthz, /v1/meta
│       └── video.py      # /v1/video/{bvid}
└── tests/
    ├── conftest.py       # 跑完整 lifespan + 关掉 auto buvid
    └── test_video.py
```

## 已知限制 / 下一步

- 只有视频信息一个端点；播放地址、弹幕、用户、直播按 PLAN.md §7 逐步加。
- **没有缓存**（连单飞也没有）：并发打同一个 BV 会各自打一次上游。按 PLAN.md §6.3，第一版可以先不缓存，等 `/v1/metrics` 命中率数据出来再说。
- **没有熔断**：连续 `-412` 不会自我冷却，只有 SDK 的 wbi 重试（`-403`）。
- 匿名模式：`playurl` 清晰度受限、历史弹幕/关注列表等需要登录的端点不可用。
- 无 Dockerfile、无 systemd/计划任务自启。
