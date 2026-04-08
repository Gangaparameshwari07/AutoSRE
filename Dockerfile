# Use Python 3.11 slim to keep the image size small
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your project files into the container
COPY . .

# Expose the port your FastAPI server uses
EXPOSE 7860

# Start the canonical FastAPI app used for deployment
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
