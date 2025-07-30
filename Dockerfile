# Dockerfile

# 1. Use an official, slim Python base image
FROM python:3.11-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy the requirements file and install dependencies first
# This is a Docker best practice that speeds up future builds
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy your application code into the container's working directory
# CHANGE: Instead of "COPY . .", we now copy only the contents of the 'app' folder.
# The source is './app' from your project root.
# The destination is '.' which refers to the current WORKDIR ('/app').
COPY ./app .

# 6. Expose the port the app will run on
# Cloud Run expects this to be 8080 by default
EXPOSE 8080

# 7. Define the command to run your application using a production server (Gunicorn)
# This command now works because main.py is correctly located at /app/main.py
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8080"]