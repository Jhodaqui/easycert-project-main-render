# Imagen base de Python 3.10
FROM python:3.10-slim

# Variables de entorno base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para librerías como weasyprint, magic y reportlab
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

# Crear el directorio del proyecto
WORKDIR /app

# Copiar los requerimientos
COPY requirements.txt /app/

# Instalar dependencias de Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto del proyecto
COPY . /app

# --- Crear archivo Python para el superusuario automático ---
RUN printf "%s\n" \
"from django.contrib.auth import get_user_model" \
"import os" \
"User = get_user_model()" \
"email = os.getenv('ADMIN_EMAIL', 'admin@example.com')" \
"password = os.getenv('ADMIN_PASS', 'admin123')" \
"nombres = os.getenv('ADMIN_NAME', 'Administrador')" \
"apellidos = os.getenv('ADMIN_LAST', 'Principal')" \
"if not User.objects.filter(email=email).exists():" \
"    User.objects.create_superuser(email=email, password=password, nombres=nombres, apellidos=apellidos)" \
"    print(f'✅ Superusuario creado con email: {email}')" \
"else:" \
"    print(f'ℹ️ El superusuario con email {email} ya existe')" \
> create_superuser.py

# Exponer el puerto 8000
EXPOSE 8000

# Comando de inicio del contenedor
CMD bash -c "python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    python manage.py shell < create_superuser.py && \
    gunicorn easycert.wsgi:application --bind 0.0.0.0:8000"
