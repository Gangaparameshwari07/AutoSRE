FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic python-dotenv openai pyyaml

# Copy all files
COPY . .

# Expose the port
EXPOSE 7860

# Run the server directly
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]