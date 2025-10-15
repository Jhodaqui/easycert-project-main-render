# Imagen base ligera y estable
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para librerías como WeasyPrint, pdfplumber, etc.
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

# Crear y definir el directorio de trabajo
WORKDIR /app

# Copiar dependencias y instalarlas
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar todo el código fuente del proyecto
COPY . /app

# Crear script para generar superusuario automáticamente
RUN printf "%s\n" \
"from django.contrib.auth import get_user_model" \
"import os" \
"User = get_user_model()" \
"email = os.getenv('ADMIN_EMAIL', 'admin@example.com')" \
"password = os.getenv('ADMIN_PASS', 'admin123')" \
"if not User.objects.filter(email=email).exists():" \
"    User.objects.create_superuser(email=email, password=password, nombres='Admin', apellidos='Root')" \
"    print(f'✅ Superusuario creado: {email}')" \
"else:" \
"    print(f'ℹ️ El superusuario {email} ya existe')" > create_superuser.py

# Comando de inicio:
#  - Ejecuta migraciones (sin borrar datos)
#  - Recolecta archivos estáticos
#  - Crea el superusuario si no existe
#  - Inicia Gunicorn optimizado para Render Free Tier
CMD bash -c "python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    python manage.py shell < create_superuser.py && \
    gunicorn easycert.wsgi:application --bind 0.0.0.0:$PORT --workers=2 --threads=2 --timeout=120"
