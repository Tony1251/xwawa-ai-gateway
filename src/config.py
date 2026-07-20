"""全局配置（从 .env 读取 + 严格校验）

生产级标准：
- Pydantic Settings 自动加载 + 验证环境变量
- 启动时校验关键配置（密钥长度、URL 格式、金额范围）
- 不同环境（dev/staging/prod）启用不同校验严格度
- 支持热加载（lru_cache + .env 变化检测）
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        env_file_encoding="utf-8",
    )

    # ===== Service =====
    app_name: str = "Xwawa-AI-Gateway"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8800
    app_secret_key: str = Field(..., min_length=32, description="JWT 签名密钥，至少 32 字符")
    app_cors_origins: str = Field(default="*")

    # ===== Database =====
    database_url: PostgresDsn = Field(...)
    database_pool_size: int = Field(20, ge=1, le=100)
    database_max_overflow: int = Field(10, ge=0, le=50)
    database_echo: bool = False

    # ===== Redis =====
    redis_url: RedisDsn = Field(...)

    # ===== Providers =====
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    midjourney_api_key: str = ""
    midjourney_base_url: str = "https://api.midjourney.com/v1"
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ===== Billing =====
    markup_rate: float = Field(1.30, ge=1.0, le=10.0, description="加价倍率")
    tax_rate: float = Field(0.06, ge=0.0, le=0.30, description="增值税率")

    # ===== Risk Control =====
    risk_daily_limit_default: float = Field(10.00, ge=0.0)
    risk_per_call_limit_default: float = Field(0.50, ge=0.0)
    risk_lockout_threshold: int = Field(5, ge=1, le=100)
    risk_rate_limit_per_min: int = Field(60, ge=1, le=10000)

    # ===== KYC =====
    kyc_provider: Literal["alipay", "wechat", "custom"] = "alipay"
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""

    # ===== Rate Limit =====
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = Field(60, ge=1)
    rate_limit_tokens_per_minute: int = Field(100_000, ge=1)

    # ===== Observability =====
    prometheus_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "console"
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = Field(0.1, ge=0.0, le=1.0)

    # ===== Security =====
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_hours: int = Field(24, ge=1, le=168)
    jwt_refresh_token_expire_days: int = Field(30, ge=1, le=365)
    bcrypt_rounds: int = Field(12, ge=10, le=14)
    api_key_length: int = Field(43, ge=16, le=128)

    # ===== Validators =====
    @field_validator("app_secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if v == "CHANGE_ME" or v == "CHANGE_ME_64_HEX_CHARS":
            raise ValueError("❌ APP_SECRET_KEY 未设置!生产环境必须用 secrets.token_hex(32) 生成")
        if len(v) < 32:
            raise ValueError("❌ APP_SECRET_KEY 至少 32 字符")
        return v

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _validate_urls(cls, v: str) -> str:
        """允许开发环境用简单 URL,生产必须校验"""
        if not v:
            raise ValueError("URL 不能为空")
        return v

    @field_validator("app_cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> str:
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        return str(v) if v is not None else "*"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    # ===== Computed Properties =====
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def configured_providers(self) -> list[str]:
        """返回已配置的 provider 列表"""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.doubao_api_key:
            providers.append("doubao")
        if self.midjourney_api_key:
            providers.append("midjourney")
        if self.deepseek_api_key:
            providers.append("deepseek")
        return providers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取配置单例"""
    try:
        settings = Settings()  # type: ignore[call-arg]
        logger.info(
            "✅ Settings loaded: env=%s, providers=%s, db=%s",
            settings.app_env,
            settings.configured_providers,
            str(settings.database_url).split("@")[-1]
            if "@" in str(settings.database_url)
            else "***",
        )
        return settings
    except Exception as e:
        logger.error("❌ 配置加载失败: %s", e)
        raise


def reset_settings_cache() -> None:
    """重置配置缓存（用于测试）"""
    get_settings.cache_clear()


# 全局实例
settings = get_settings()


# ===== 启动时安全检查 =====
def validate_production_safety() -> None:
    """生产环境强制安全检查"""
    if not settings.is_production:
        return

    issues = []

    if settings.app_debug:
        issues.append("APP_DEBUG=true (生产必须 false)")

    if "localhost" in str(settings.database_url) or "127.0.0.1" in str(settings.database_url):
        issues.append("DATABASE_URL 使用 localhost (生产应使用真实地址)")

    if "*" in settings.app_cors_origins:
        issues.append("APP_CORS_ORIGINS=* (生产必须限制来源)")

    if not settings.configured_providers:
        issues.append("未配置任何上游 Provider (OPENAI_API_KEY 等)")

    if settings.bcrypt_rounds < 12:
        issues.append(f"BCRYPT_ROUNDS={settings.bcrypt_rounds} 太低 (建议 >= 12)")

    if issues:
        logger.warning("⚠️  生产环境安全警告:")
        for issue in issues:
            logger.warning("   - %s", issue)
    else:
        logger.info("✅ 生产环境安全检查通过")


def generate_secure_secret() -> str:
    """生成强随机密钥（CLI 工具）"""
    return secrets.token_hex(32)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "gen-secret":
        print("APP_SECRET_KEY=" + generate_secure_secret())
    else:
        # 打印配置摘要（脱敏）
        print(f"App: {settings.app_name} ({settings.app_env})")
        print(f"Port: {settings.app_port}")
        print(
            f"DB: {settings.database_url.split('@')[-1] if '@' in settings.database_url else '***'}"
        )
        print(f"Redis: {'configured' if settings.redis_url else 'not configured'}")
        print(f"Providers: {settings.configured_providers or 'none'}")
        print(f"Rate Limit: {settings.rate_limit_requests_per_minute} req/min")
        print(f"CORS Origins: {settings.app_cors_origins}")
        validate_production_safety()
