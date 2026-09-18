# Run SynFinder anywhere that takes a container:
#   docker build -t synfinder . && docker run -p 8501:8501 synfinder
#
# Also what Hugging Face Spaces / Render / Fly.io build from.
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
COPY catalog ./catalog

RUN pip install --no-cache-dir -e ".[web]"

# Hugging Face Spaces expects 7860; everything else defaults to 8501.
ENV PORT=8501
EXPOSE 8501

CMD ["sh", "-c", "python -m uvicorn synfinder.web:app --host 0.0.0.0 --port ${PORT} --app-dir /app/src"]
