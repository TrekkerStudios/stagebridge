# Use bun base img
FROM oven/bun:1.2-debian

# Install Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv libasound2 libasound2-dev && \
    rm -rf /var/lib/apt/lists/*

# Set up backend
WORKDIR /app/backend
RUN python3 -m venv venv
ENV PATH="/app/backend/venv/bin:$PATH"
COPY components/python/client_backend/requirements.txt .
RUN /app/backend/venv/bin/pip install --upgrade pip && \
    /app/backend/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY components/python/client_backend/ .

# Set up frontend
WORKDIR /app/frontend
COPY components/bun/client_frontend/ .
RUN bun install

# Back to global
WORKDIR /app
RUN bun add -g concurrently

EXPOSE 3000 3001

# Start both apps
CMD ["concurrently", "--kill-others", "--names", "backend,frontend", \
     "python3 backend/main.py", "bun run --cwd ./frontend start"]