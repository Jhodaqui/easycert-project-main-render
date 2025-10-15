import os
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin
)
from django.conf import settings

from django.apps import apps

TIPOS_DOCUMENTO = [
    ('CC', 'Cédula de ciudadanía'),
    ('TI', 'Tarjeta de identidad'),
    ('CE', 'Cédula de extranjería'),
    ('PA', 'Pasaporte'),
]


# ----------------------
# Modelos de geografía
# ----------------------
class dptos(models.Model):
    idDepto = models.CharField(primary_key=True, max_length=20, unique=True)
    nombreDepto = models.CharField(max_length=100)

    def __str__(self):
        return self.nombreDepto


class municipios(models.Model):
    idMpio = models.AutoField(primary_key=True)
    nombreMpio = models.CharField(max_length=100)
    idDepto = models.ForeignKey(dptos, on_delete=models.CASCADE, related_name="municipios")
    # En tu esquema actual los "centros" están almacenados en este campo
    nombreCentro = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        # mostramos municipio (pero el campo nombreCentro existe y lo usaremos para listar centros)
        return self.nombreMpio

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# ----------------------
# User manager (igual que tenías)
# ----------------------
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El usuario debe tener un correo electrónico")

        email = self.normalize_email(email)

        Rol = apps.get_model("users", "Rol")  # evita import circular

        # 🔹 Si no se pasa role, asignar "Usuario"
        if "role" not in extra_fields or extra_fields["role"] is None:
            role, _ = Rol.objects.get_or_create(nombre="Usuario")
            extra_fields["role"] = role

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        Rol = apps.get_model("users", "Rol")

        # 🔹 Superuser siempre con rol "Administrador"
        role, _ = Rol.objects.get_or_create(nombre="Administrador")
        extra_fields["role"] = role

        return self.create_user(email, password, **extra_fields)

# ----------------------
# CustomUser (añadidos departamento y centro)
# ----------------------
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Campos personales
    nombres = models.CharField("Nombres", max_length=100)
    apellidos = models.CharField("Apellidos", max_length=100)
    tipo_documento = models.CharField("Tipo de documento", max_length=10, choices=TIPOS_DOCUMENTO)
    numero_documento = models.CharField("Número de documento", max_length=15, unique=True)
    email = models.EmailField("Correo electrónico", unique=True)

    # 🔹 Relación a roles dinámicos
    role = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True, related_name="usuarios")

    # Relación con departamento y centro
    departamento = models.ForeignKey("dptos", on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    centro = models.ForeignKey("municipios", on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_centro')

    # Estado
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombres", "apellidos", "tipo_documento", "numero_documento"]

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.numero_documento})"

    def get_tipo_documento_display_full(self):
        return dict(TIPOS_DOCUMENTO).get(self.tipo_documento, self.tipo_documento)

# ----------------------
# Constancia (igual que tenías)
# ----------------------
class Constancia(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("en_proceso", "En Proceso"),
        ("firmada", "Firmada"),
        ("rechazada", "Rechazada"),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fecha_inicial = models.DateField()
    fecha_final = models.DateField()
    comentario = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario} ({self.fecha_inicial} → {self.fecha_final}) - {self.estado}"
