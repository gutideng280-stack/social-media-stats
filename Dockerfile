# 使用 Playwright 官方 Python 镜像（预装 Chromium 系统依赖）
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 设置工作目录
WORKDIR /app/backend

# 暴露端口（Render 通过 PORT 环境变量传入）
ENV PORT=10000
EXPOSE 10000

# 启动命令
CMD ["python", "app.py"]
