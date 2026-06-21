FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project  # deps first (better layer caching)
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PORT=8001
EXPOSE 8001
CMD ["uv", "run", "carbon-agent"]