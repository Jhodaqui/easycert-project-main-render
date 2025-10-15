import os
from django.conf import settings

def crear_carpetas(usuario):
    # Suponemos que el número de documento está en 'numero_documento'
    numero_documento = usuario.numero_documento

    # Ruta base donde se van a crear las carpetas
    base_path = os.path.join(settings.MEDIA_ROOT, 'usuarios', numero_documento)

    # Crear la carpeta principal si no existe
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    # Crear las subcarpetas 'individual' y 'bloques'
    subcarpeta_individual = os.path.join(base_path, 'individual')
    subcarpeta_bloques = os.path.join(base_path, 'bloques')

    if not os.path.exists(subcarpeta_individual):
        os.makedirs(subcarpeta_individual)

    if not os.path.exists(subcarpeta_bloques):
        os.makedirs(subcarpeta_bloques)