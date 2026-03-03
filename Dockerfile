FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy entire source first (needed for editable install)
COPY . .

# Install Python deps (includes langchain, langgraph, langchain-groq)
RUN pip install --no-cache-dir -e ".[dev]"

# Create data directories
RUN mkdir -p data/cache data/db data/feature_cache models/artifacts

ENV PYTHONPATH=/app
EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
