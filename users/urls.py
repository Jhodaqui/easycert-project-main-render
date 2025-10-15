from django.urls import path
from .views import (
    register_view, login_view, logout_view, home_view,
    password_reset_request_view, password_reset_confirm_view,
    admin_dashboard, staff_dashboard, user_dashboard,
    mostrar_formulario_constancia, procesar_constancia,
    datos_bulk_upload, user_dashboard_solicitud,
    manage_roles, cargar_centros  # Se añadió cargar_centros
)

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("home/", home_view, name="home"),
    path("password-reset/", password_reset_request_view, name="password_reset"),
    path("reset/<uidb64>/<token>/", password_reset_confirm_view, name="password_reset_confirm"),

    # vistas para la gestión de roles y dashboards
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("datos/upload/", datos_bulk_upload, name="datos_bulk_upload"),
    path("staff-dashboard/", staff_dashboard, name="staff_dashboard"),
    path("user-dashboard/", user_dashboard, name="user_dashboard"),
    
    path("formulario-constancia/", mostrar_formulario_constancia, name="formulario_constancia"),
    path("procesar-constancia/", procesar_constancia, name="procesar_constancia"),

    path("user-dashboard/solicitud/", user_dashboard_solicitud, name="user_dashboard_solicitud"),
    path("manage-roles/", manage_roles, name="manage_roles"),

    # Nueva ruta para AJAX de municipios/centros
    path("cargar-centros/", cargar_centros, name="cargar_centros"),
]
