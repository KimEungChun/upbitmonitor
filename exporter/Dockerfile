# ./exporter/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY exporter_up.py .
RUN pip install flask requests
CMD ["python", "exporter_up.py"]