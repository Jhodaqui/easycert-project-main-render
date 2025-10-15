from django.db import models
from django.conf import settings
from documents.models import Contrato
import os

# Create your models here.

class Certificado(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificados"
    )
    contrato = models.ForeignKey(Contrato, on_delete=models.SET_NULL, null=True, blank=True)
    numero = models.PositiveIntegerField(unique=True, null=True, blank=True)  # consecutivo
    archivo = models.FileField(upload_to="certificates/", blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Certificado {self.usuario.numero_documento} - {self.creado_en.date()}"

    def numero_formateado(self):
        return str(self.numero).zfill(3) if self.numero else "---"
    
class CertificadoMerge(models.Model):
    usuario_id = models.IntegerField()
    nombre_completo = models.CharField(max_length=150)
    tipo_documento = models.CharField(max_length=10)
    numero_documento = models.CharField(max_length=15)
    email = models.EmailField()
    numero_certificado = models.IntegerField(null=True)
    fecha_certificado = models.DateTimeField(null=True)
    fecha_inicio = models.DateField(null=True)
    fecha_fin = models.DateField(null=True)
    campo = models.CharField(max_length=255, null=True)
    valor = models.TextField(null=True)

    class Meta:
        managed = False  # importante: Django no toca la vista
        db_table = "vw_certificado_merge"