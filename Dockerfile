# Imagen base
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias
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

# --- Crear script para superusuario automático ---
RUN echo "from django.contrib.auth import get_user_model; \
import os; \
User = get_user_model(); \
username = os.getenv('ADMIN_USER', 'admin'); \
email = os.getenv('ADMIN_EMAIL', 'admin@example.com'); \
password = os.getenv('ADMIN_PASS', 'admin123'); \
\
u = User.objects.filter(username=username); \
\
if not u.exists(): \
    User.objects.create_superuser(username=username, email=email, password=password); \
    print('✅ Superusuario creado:', username); \
else: \
    print('ℹ️ El superusuario ya existe:', username)" \
> create_superuser.py

# Puerto de salida
EXPOSE 8000

# Comando de inicio automatizado
CMD bash -c "
python manage.py migrate --noinput &&
python manage.py collectstatic --noinput &&
python manage.py shell < create_superuser.py &&
gunicorn easycert.wsgi:application --bind 0.0.0.0:8000 --workers 3
"
