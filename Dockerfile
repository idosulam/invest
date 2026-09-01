FROM python:3.11-slim

WORKDIR /app

# System deps for TA-Lib, PostgreSQL client, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib && ./configure --prefix=/usr && make && make install \
    && cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
