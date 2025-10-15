from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import StaffFillForm, ManualFieldsForm, ConstanciaGenerateForm
from .models import Certificado
from documents.models import UserContractData
from django.core.files.base import ContentFile
from docx import Document
import io
from users.models import CustomUser
import os
from django.db.models import Max
from .utils import fill_word_template  # función que llena borrador.docx
from django.conf import settings


# Create your views here.

@login_required
def generar_constancia(request, user_id):
    user_data = UserContractData.objects.filter(usuario_id=user_id)
    data_dict = {d.campo: d.valor for d in user_data}

    if request.method == "POST":
        form = StaffFillForm(request.POST)
        if form.is_valid():
            data_dict.update(form.cleaned_data)

            # Cargar borrador
            doc = Document("media/templates/borrador.docx")

            # Reemplazar marcadores (ej. {{numero_contrato}})
            for p in doc.paragraphs:
                for key, value in data_dict.items():
                    marcador = f"{{{{{key}}}}}"
                    if marcador in p.text:
                        p.text = p.text.replace(marcador, str(value))

            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            certificado = Certificado.objects.create(
                usuario_id=user_id,
                archivo=ContentFile(buffer.read(), f"certificado_{user_id}.docx")
            )

            return redirect("staff_dashboard")
    else:
        form = StaffFillForm()

    return render(request, "certificates/generar_constancia.html", {"form": form, "user_id": user_id})

@login_required
def manual_fields_view(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)

    if request.method == "POST":
        form = ManualFieldsForm(request.POST)
        if form.is_valid():
            for campo, valor in form.cleaned_data.items():
                UserContractData.objects.update_or_create(
                    usuario=usuario,
                    campo=campo,
                    defaults={"valor": valor}
                )
            messages.success(request, "Campos manuales guardados.")
            return redirect("certificates:generar_constancia", user_id=usuario.id)
    else:
        form = ManualFieldsForm()

    return render(request, "certificates/manual_fields.html", {"form": form, "usuario": usuario})


@login_required
def generar_constancia_view(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)
    user_data = UserContractData.objects.filter(usuario=usuario)

    if request.method == "POST":
        form = ConstanciaGenerateForm(request.POST)
        if form.is_valid():
            # Consecutivo
            last_num = Certificado.objects.aggregate(max_num=Max("numero"))["max_num"] or 0
            next_num = last_num + 1

            cert, created = Certificado.objects.get_or_create(
                usuario=usuario,
                defaults={"numero": next_num}
            )

            # Contexto para el Word
            context = {
                "numero_certificacion": cert.numero_formateado(),
                "nombre_completo": usuario.nombre_completo,
                "tipo_documento": usuario.tipo_documento,
                "numero_documento": usuario.numero_documento,
                # Manual (de forms previos o StaffFillForm)
                "numero_contrato": user_data.filter(campo="numero_contrato").first().valor if user_data.filter(campo="numero_contrato").exists() else "",
                "fecha_contrato": user_data.filter(campo="fecha_contrato").first().valor if user_data.filter(campo="fecha_contrato").exists() else "",
                "fecha_expedicion_texto": user_data.filter(campo="fecha_expedicion").first().valor if user_data.filter(campo="fecha_expedicion").exists() else "",
                # Más campos del PDF
                **{d.campo: d.valor for d in user_data}
            }

            # Generar Word
            output_path = os.path.join(settings.MEDIA_ROOT, "certificados", f"cert_{cert.numero_formateado()}.docx")
            fill_word_template(context, output_path)

            # Guardar archivo
            with open(output_path, "rb") as f:
                cert.archivo.save(os.path.basename(output_path), f, save=True)

            messages.success(request, f"Constancia generada con éxito. N° {cert.numero_formateado()}")
            return redirect("staff_dashboard")
    else:
        form = ConstanciaGenerateForm()

    return render(request, "certificates/generar_constancia.html", {
        "form": form,
        "usuario": usuario,
        "user_data": {d.campo: d.valor for d in user_data}
    })

