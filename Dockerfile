# Use official Python image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and group with a home directory
RUN adduser --system --group --home /app appuser

# Set permissions for the application directory for the non-root user
RUN chown -R appuser:appuser /app

# Create .streamlit directory with proper permissions
RUN mkdir -p /app/.streamlit && chown -R appuser:appuser /app/.streamlit

# Create cache directory for HuggingFace models
RUN mkdir -p /app/.cache && chown -R appuser:appuser /app/.cache

# Switch to the non-root user
USER appuser

# Copy project files
COPY . /app

# Set HOME environment variable to /app
ENV HOME=/app

# Set HuggingFace cache directory
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers
ENV HF_DATASETS_CACHE=/app/.cache/huggingface/datasets

# Expose Streamlit port
EXPOSE 8501

# Streamlit-specific environment variables
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
