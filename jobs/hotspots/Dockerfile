FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY run.py .
# Configuration comes from environment variables at run time (never baked into the image).
CMD python run.py
