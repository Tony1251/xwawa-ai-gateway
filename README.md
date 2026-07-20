# xwawa-ai-gateway

AI Agent 信用支付网关 - 管理 AI API 调用、余额扣费、风控和用量监控。

## 功能特性

- 🤖 **多 AI 服务商支持**: OpenAI / Anthropic / 豆包 / DeepSeek / Midjourney
- 💰 **信用扣费系统**: 余额检查、日限额/单次限额、Z-Score 异常检测
- 🔑 **双认证机制**: JWT + API Key (bcrypt 哈希存储)
- 🚌 **智能路由**: 模型名自动路由到最优 Provider
- 💳 **支付网关**: Mock 支付 (MVP)，可扩展支付宝/微信/Stripe
- 📊 **用量审计**: 完整调用日志、异常标记、Prometheus 指标
- 🛡️ **安全**: 生产环境安全校验、统一错误响应、滑动窗口限流
- 🌐 **三端前端**: Admin 管理面板 / 用户门户 / 微信小程序

## 技术栈

**后端**: Python 3.11+ / FastAPI 0.115 / SQLAlchemy async / asyncpg / Redis / Alembic

**前端**: React 18 + Vite + React Router + React Query + Axios

**基础设施**: PostgreSQL / Redis / Caddy (反向代理) / Prometheus / Grafana

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### 1. 克隆 & 配置

```bash
git clone https://github.com/Tony1251/xwawa-ai-gateway.git
cd xwawa-ai-gateway

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入必要的密钥和 URL
```

### 2. 启动服务 (Docker)

```bash
docker compose up -d
```

服务端口:

| 服务 | 端口 | 说明 |
|------|------|------|
| app | 8800 | FastAPI 后端 |
| postgres | 5433 | PostgreSQL |
| redis | 6381 | Redis |
| caddy | 80/443 | 反向代理 |
| prometheus | 9090 | 指标采集 |
| grafana | 3000 | 可视化面板 |

### 3. 初始化数据库

```bash
docker compose exec app alembic upgrade head
```

### 4. 访问

- API 文档: http://localhost:8800/docs
- Admin 前端: http://localhost:3001 (需启动 admin-frontend)
- 用户前端: http://localhost:3002 (需启动 user-frontend)

### 本地开发

```bash
# 后端
cd src
pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8800

# 前端 (admin)
cd admin-frontend && npm install && npm run dev

# 前端 (user)
cd user-frontend && npm install && npm run dev
```

## API 概览

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/auth/register` | 用户注册 |
| POST | `/v1/auth/login` | 登录 (返回 JWT) |
| POST | `/v1/auth/api-keys` | 创建 API Key |
| GET | `/v1/auth/api-keys` | 列出 API Keys |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat` | 发送对话请求 |
| GET | `/v1/models` | 列出可用模型 |

### 钱包

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/wallet/balance` | 查询余额 |
| POST | `/v1/wallet/recharge` | 充值 (Mock) |
| GET | `/v1/wallet/transactions` | 交易记录 |
| GET | `/v1/wallet/usage` | 用量明细 |
| POST | `/v1/wallet/agents` | 注册 Agent |

### 管理 (Admin)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/users` | 用户列表 |
| POST | `/admin/users/{id}/lock` | 锁定用户 |
| POST | `/admin/users/{id}/unlock` | 解锁用户 |
| GET | `/admin/users/{id}/api-keys` | 用户 API Keys |
| GET | `/admin/users/{id}/usage` | 用户用量 |
| GET | `/admin/stats/overview` | 统计概览 |

## 项目结构

```
xwawa-ai-gateway/
├── src/
│   ├── main.py              # FastAPI 入口 + lifespan
│   ├── config.py            # Pydantic Settings
│   ├── db.py                # 异步数据库连接池
│   ├── exceptions.py        # BusinessError 体系
│   ├── middlewares.py        # CORS / Request ID / 日志
│   ├── middlewares_rate_limit.py  # Redis 滑动窗口限流
│   ├── logging_config.py     # structlog 配置
│   ├── api/v1/              # REST API 路由
│   ├── auth/                # JWT + API Key 认证
│   ├── wallet/              # 钱包/CRUD/CreditService
│   ├── billing/             # 定价引擎
│   ├── providers/           # AI Provider 实现
│   ├── routing/             # 模型路由
│   ├── audit/              # 审计日志 + ML 异常检测
│   ├── payment/            # 支付网关 (Mock)
│   └── a2a/                # Agent-to-Agent 协议
├── admin-frontend/          # Admin 管理面板 (React)
├── user-frontend/          # 用户门户 (React)
├── alembic/                # 数据库迁移
├── scripts/                # 工具脚本
├── tests/                  # 单元测试
├── docker-compose.yml       # 6 服务编排
├── Dockerfile              # 多阶段构建
├── Caddyfile             # 反向代理配置
└── pyproject.toml        # 项目配置
```

## 配置项 (.env)

核心配置项:

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接串 | `redis://...` |
| `APP_SECRET_KEY` | JWT 密钥 (≥32字符) | `openssl rand -hex 64` |
| `MARKUP_RATE` | 加价倍率 | `1.30` |
| `TAX_RATE` | 增值税率 | `0.06` |
| `APP_CORS_ORIGINS` | CORS 允许域名 | `https://admin.example.com` |

## 部署

### Docker Compose (生产)

```bash
# 编辑 .env 中的生产配置
# 编辑 Caddyfile 中的域名
./deploy.sh
```

### 定价模型

| 模型 | Provider | 输入 ($/1M tokens) | 输出 ($/1M tokens) |
|------|----------|-------------------|-------------------|
| GPT-4o | OpenAI | $2.50 | $10.00 |
| GPT-4o Mini | OpenAI | $0.15 | $0.60 |
| Claude Sonnet 4 | Anthropic | $3.00 | $15.00 |
| 豆包 Pro 32K | 豆包 | ¥0.001 | ¥0.002 |
| DeepSeek Chat | DeepSeek | ¥0.001 | ¥0.002 |

用户价格 = Provider 价格 × 加价倍率 × (1 + 增值税率)

## CI/CD

GitHub Actions 流水线:

- **Ruff**: 代码 lint
- **MyPy**: 静态类型检查
- **Pytest**: 单元测试
- **Docker Build**: 镜像构建

## 许可证

MIT
