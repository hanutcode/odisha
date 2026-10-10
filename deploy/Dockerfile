FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git g++ && rm -rf /var/lib/apt/lists/*
COPY requirements-web.txt requirements.txt requirements-model.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-web.txt -r /tmp/requirements.txt -r /tmp/requirements-model.txt gunicorn==23.0.0 whitenoise==6.9.0
ENV HOME=/tmp
WORKDIR /app/web
CMD ["gunicorn", "iris_web.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "180", "--access-logfile", "-"]
