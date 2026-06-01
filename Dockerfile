FROM python:3.11-slim

WORKDIR /app

COPY BACK/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY BACK/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
