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

# The command to start your control plane on port 7860
CMD ["python", "server.py"]
