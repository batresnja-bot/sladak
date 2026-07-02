FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml requirements.txt requirements-web.txt ./
COPY turnitin_diy ./turnitin_diy

RUN pip install --no-cache-dir -r requirements-web.txt gunicorn

EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "turnitin_diy.webapp:create_app()"]
