# Imagen base de Python 3.10 (ligera y estable)
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para algunas librerías
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

# Crear directorio de la app
WORKDIR /app

# Copiar archivos de requerimientos e instalarlos
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar todo el proyecto
COPY . /app

# Generar script de creación automática del superusuario
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

# Recolectar estáticos y ejecutar migraciones
RUN python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    python manage.py shell < create_superuser.py

# Comando de inicio (ligero y optimizado)
CMD gunicorn easycert.wsgi:application --bind 0.0.0.0:$PORT --workers=2 --threads=2 --timeout=120
