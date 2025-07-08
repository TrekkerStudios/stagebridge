# Use a minimal Debian base image
FROM debian:bullseye-slim

# Install Python and ALSA libraries
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv libasound2 libasound2-dev && \
    rm -rf /var/lib/apt/lists/*

# Set up backend
WORKDIR /app

# Create and activate venv, set PATH
RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# Install Python dependencies
COPY components/python/stagebridge/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY components/python/stagebridge/ .

# Expose backend port (adjust as needed)
EXPOSE 3000 3001

# Start the backend
CMD ["python", "main.py"]