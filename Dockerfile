FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8080

# Run the web server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
