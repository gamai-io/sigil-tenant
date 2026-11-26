FROM python:3.12-slim
WORKDIR /app
COPY tenant_api.py /app/tenant_api.py
ENV TENANT_API_HOST=0.0.0.0 TENANT_API_PORT=18400 PYTHONUNBUFFERED=1 SANDBOX_IMG=alpine:latest
EXPOSE 18400
CMD ["python3","/app/tenant_api.py"]
