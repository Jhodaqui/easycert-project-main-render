# Imagen base: Python 3.10
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para las librerías
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    libmagic-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar dependencias
COPY requirements.txt /app/

# Instalar dependencias Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copiar el proyecto completo
COPY . /app

# Variables de entorno básicas
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=easycert.settings

# Recolectar archivos estáticos (no falla si no hay)
RUN python manage.py collectstatic --no-input || true

# Puerto
EXPOSE 8000

# Comando de inicio
CMD ["gunicorn", "easycert.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
