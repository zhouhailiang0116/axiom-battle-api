FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with gunicorn
ENV PORT=8000
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "1"]
