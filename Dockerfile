FROM python:3.14-slim

WORKDIR /app

# Install dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY server.py .

EXPOSE 5000

CMD ["python", "-u", "server.py"]
