FROM python:3.12-slim

WORKDIR /app
COPY main.py /app/main.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python3", "-u", "/app/main.py"]
