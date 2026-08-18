# A container is your app plus its exact dependencies, packaged so it runs
# identically anywhere. Deployment platforms expect one.

# "slim" = minimal Debian. The full python image is ~1GB; slim is ~150MB.
FROM python:3.12-slim

WORKDIR /app

# Copy requirements FIRST, install, then copy the code.
# Docker caches each step. Code changes far more often than dependencies,
# so this ordering means a code edit does not reinstall everything.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Documentation only - does not actually publish the port.
EXPOSE 8000

# 0.0.0.0 means "accept connections from outside the container".
# 127.0.0.1 would only accept from inside it, and nothing could reach you.
# $PORT is set by Render/Railway; 8000 is the local fallback.
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
