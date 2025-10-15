from django.urls import path
from . import views

app_name = "certificates"

urlpatterns = [
    path("manual/<int:user_id>/", views.manual_fields_view, name="manual_fields"),
    path("generar/<int:user_id>/", views.generar_constancia_view, name="generar_constancia"),
]
