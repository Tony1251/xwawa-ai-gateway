[# 📝 更新日志

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-19

### Added
- **完整后端核心模块**
  - `src/wallet/`: 数据模型 + CRUD + CreditService 扣费引擎
  - `src/billing/`: 定价引擎（OpenAI/Anthropic/豆包/DeepSeek/Midjourney）
  - `src/providers/`: Provider 抽象层 + 5 家 AI 服务商实现
  - `src/routing/`: 模型路由（精确匹配 + 前缀匹配 + 回退策略）
  - `src/audit/`: 审计日志 + Z-Score ML 异常检测
  - `src/a2a/`: Agent-to-Agent 通信协议
  - `src/payment/`: Mock 支付网关（可扩展支付宝/微信/Stripe）
  - `src/api/v1/`: 7 套 REST API（auth/chat/wallet/ws/a2a/payment/admin）
  - `src/exceptions.py`: BusinessError 体系 + 全局异常处理器
  - `src/main.py`: FastAPI 入口 + lifespan（启动/关闭管理）
  - `src/middlewares_rate_limit.py`: Redis 滑动窗口限流
  - `src/logging_config.py`: structlog 结构化日志

- **数据库迁移**: Alembic 迁移文件（6 张表：users/wallets/transactions/api_keys/agents/usage_logs）

- **工程化**
  - `pyproject.toml`: 完整项目配置（依赖/lint/mypy/pytest）
  - `.gitignore` / `.dockerignore`
  - `src/api/v1/schemas.py`: Pydantic 统一 API Schema
  - `.github/workflows/ci.yml`: GitHub Actions CI（ruff/mypy/pytest/docker build）

- **测试**: `tests/test_core.py` 覆盖 pricing/routing/api_key/anomaly/payment

### Features
- JWT + API Key 双认证机制
- 信用扣费（日限额/单次限额/余额检查/异常检测）
- 模型自动路由（根据模型名路由到最优 Provider）
- 加价倍率 + 增值税率自动计算用户价格
- WebSocket 实时对话
- Admin 管理面板（用户管理/统计/锁定）
- 支付订单（Mock 直接到账，MVP 阶段不接真实支付）

### Security
- `app_secret_key` 长度≥32 强制校验
- 生产环境安全检查（validate_production_safety）
- 统一错误响应（不泄漏敏感信息）
- bcrypt 密码哈希（可配置 rounds）
- API Key 哈希存储（SHA-256）

### Observability
- JSON 结构化日志（request_id/user_id 注入）
- Prometheus `/metrics` 端点
- Sentry 可选集成
- 慢请求告警（>1s）
- 审计日志（auth/payment/risk/anomaly）
- Z-Score 异常检测（费用/频率/失败率）

## [0.1.0] - 2026-07-19

### Added
- 项目初始化（Scaffold）
- 基础配置文件（config.py/db.py/logging_config.py）
