FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/ .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENV PORT=8000

CMD ["python", "main.py"]