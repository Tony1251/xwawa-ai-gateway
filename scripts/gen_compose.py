import yaml

services = {
    "postgres": {
        "image": "postgres:16-alpine",
        "environment": {
            "POSTGRES_USER": "xwawa",
            "POSTGRES_PASSWORD": "xwawa_secure_pass",
            "POSTGRES_DB": "xwU xwawa -d xwawa_db"],
            "interval": "5s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "redis": {
        "image": "redis:7-alpine",
        "ports": [" "timeout": "5s",
            "retries": 5,
        },
    },
    "app": {
        "build": {"context": ".", "dockerfile": "Dockerfile"},
        "ports": ["8800:8800"],
        "environment": {
            "DATABASE_URL": "postgresql+asyncpg://xwawa:xwawa_secure_pass@postgres:5432/xwawa_db",
            "REDIS_URL": "redis://redis:6379",
            "APP_SECRET_KEY": "${APP_SECRET_KEY:?APP_SECRET_KEY required}",
            "APP_ENV": "${APP_ENV:-development}",
            "LOG_LEVEL": "${LOG_LEVEL:-INFO}",
        },
        "depends_on": {
            "postgres": {"condition": "service_healthy"},
            "redis": {"condition": "service_healthy"},
        },
        "healthcheck": {
            "test": ["CMD", "curl", "-f", "http://localhost:8800/health"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "caddy": {
       "],
    },
    "prometheus": {
        "image": "prom/prometheus:v2.53.0",
        "ports": ["9090:9090"],
        "volumes": ["./prometheus.yml:/etc/prometheus/prometheus.yml:ro", "        "depends_on": ["prometheus"],
    },
}

compose = {
    "version": "3.9",
    "services": services,
    "volumes": {
        "postgres_data": None,
        "redis_data": None,
        "caddy_data": None,
        "prometheus_data": None,
        "grafana_data": None,
    },
}

with open("/Users/yuhengluo/Projects/xwawa-ai-gateway/docker-compose.yml", "w") as f:
    yaml.dump(compose, f, default_flow_style=False, sort_keys=False)
print("done")
