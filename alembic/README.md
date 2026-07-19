# Alembic 数据库迁移

使用方式：

```bash
# 初始化
alembic upgrade head

# 自动生成迁移（修改 models 后）
alembic revision --autogenerate -m "describe change"

# 应用迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1
```

## 迁移策略

- 每次修改 src/wallet/models.py 后，必须生成新迁移
- 不要手动编辑已应用的迁移文件
- 生产部署前必须测试 upgrade + downgrade
- 大表变更（> 100 万行）需要分批执行

## 紧急回滚

```bash
docker compose stop app
alembic downgrade -1
docker compose start app
```
