from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置，全部可用 BILI_ 前缀的环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BILI_", extra="ignore"
    )

    app_name: str = "bilibili-api-server"
    host: str = "127.0.0.1"
    port: int = 8000

    # 空字符串 = 关闭鉴权（仅本机开发建议）
    api_key: str = ""

    upstream_timeout: float = 10.0
    upstream_concurrency: int = 6
    client: str = "httpx"
    proxy: str = ""

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
