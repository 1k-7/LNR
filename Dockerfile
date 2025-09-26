# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Run the web server using Gunicorn (a production-ready server for Python)
# This is the standard way to run a Flask app on Render.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
