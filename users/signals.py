from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Rol

@receiver(post_migrate)
def crear_roles_por_defecto(sender, **kwargs):
    # 👇 Aseguramos que solo corra en la app 'users'
    if sender.name == "users":
        for nombre in ["Administrador", "Funcionario", "Usuario"]:
            Rol.objects.get_or_create(nombre=nombre)
