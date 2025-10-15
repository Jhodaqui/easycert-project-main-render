from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("upload/<int:user_id>/", views.upload_pdf_view, name="upload_pdf"),
    path("select/<int:user_id>/", views.select_data_view, name="select_data"),
    path("contrato/create-modal/", views.contrato_create_modal, name="contrato_create_modal"),
    path("contratos/<int:user_id>/", views.contratos_usuario_view, name="contratos_usuario"),
    path("contrato/prefill/", views.prefill_contrato, name="prefill_contrato"),
    path("contrato/<int:contrato_id>/", views.contrato_detail, name="contrato_detail"),
    
    path("listar-docx-guardados/<int:user_id>/", views.listar_docx_guardados, name="listar_docx_guardados"),
    path("contratos/preview/<int:user_id>/<str:filename>/", views.preview_docx, name="preview_docx"),
    path("contratos/download/<int:user_id>/<str:filename>/", views.download_and_delete_docx, name="download_docx"),
    path("contratos/upload/<int:user_id>/", views.upload_edited_docx, name="upload_docx"),
    
    path("generate-individual/<int:user_id>/", views.generate_individual_documents, name="generate_individual"),
    path("contratos/bloques/<int:user_id>/", views.generate_block_documents, name="generate_block_documents"),
    # pruebas
    path("contrato/pdf/<int:user_id>/<int:contrato_id>/", views.generar_certificado, name="generar_pdf"),
]
