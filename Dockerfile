# AI求职助手 Docker 镜像
# 构建: docker build -t ai-job-helper .
# 运行: docker run --rm -it --env-file deep_research/.env ai-job-helper

FROM python:3.12-slim

LABEL maintainer="AI求职助手"
LABEL description="基于 Orchestrator-Workers 架构的 AI 求职准备系统"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY deep_research/ ./deep_research/
COPY tests/ ./tests/
COPY research_output/ ./research_output/
COPY data/ ./data/

# 预创建必要目录
RUN mkdir -p /app/research_output /app/data

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 默认入口：打印帮助信息
ENTRYPOINT ["python", "-m", "deep_research"]
CMD ["--help"]
