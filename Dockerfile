# Step 1: Use a lightweight base image with Python 3.11
FROM python:3.11

# Step 2: Set environment variables for Python
# Prevents Python from writing .pyc files and enables bufferless logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


RUN apt-get update && \
    apt-get install -y -f mysql\* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Step 4: Set the working directory in the container
WORKDIR /app

# Step 5: Copy application files into the container
COPY . /app

# Step 6: Install Python dependencies
RUN python -m pip install --upgrade pip && \
    python -m pip install pylint discord python-dotenv mysql-connector-python

# Step 8: Set the command to run the application
CMD ["python", "main.py"]