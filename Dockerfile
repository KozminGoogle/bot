FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt && pip install alembic
ENV PYTHONUNBUFFERED=1
CMD alembic upgrade head && python main.py
