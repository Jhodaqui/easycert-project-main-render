from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.shortcuts import render,redirect
from django.contrib import messages
import pandas as pd 
from .models import CustomUser

# Register your models here.

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "nombres", "apellidos", "tipo_documento", "numero_documento", "role", "is_staff", "is_active")
    ordering = ("email",)
    search_fields = ("email", "numero_documento")
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("nombres", "apellidos", "tipo_documento", "numero_documento", "role")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombres", "apellidos", "tipo_documento", "numero_documento", "role", "password1", "password2", "is_staff", "is_active"),
        }),
    )

    # Acción personalizada
    change_list_template = "users/admin/users_bulk_upload.html"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path("upload-users/", self.admin_site.admin_view(self.upload_users), name="users_upload"),
        ]
        return custom_urls + urls

    def upload_users(self, request):
        if request.method == "POST" and request.FILES.get("file"):
            file = request.FILES["file"]
            try:
                # Cargar CSV o Excel
                df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)

                for _, row in df.iterrows():
                    CustomUser.objects.update_or_create(
                        email=row["email"],
                        defaults={
                            "nombres": row["nombres"],
                            "apellidos": row["apellidos"],
                            "tipo_documento": row["tipo_documento"],
                            "numero_documento": row["numero_documento"],
                            "role": row.get("role", "user"),
                            "is_active": True,
                        },
                    )
                messages.success(request, "Usuarios cargados correctamente.")
            except Exception as e:
                messages.error(request, f"Error al procesar el archivo: {e}")
            return redirect("..")
        return render(request, "users/admin/users_bulk_upload.html")


admin.site.register(CustomUser, CustomUserAdmin)
