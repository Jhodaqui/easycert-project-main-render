import os, json, shutil, zipfile
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.contrib import messages
from io import BytesIO
from docx import Document

from .forms import ContratoUploadForm, ContratoModalForm
from .models import TempExtractedData, UserContractData, Contrato
from users.models import CustomUser
from .utils import extract_key_value_from_pdf, extract_contract_metadata, generate_individual_docx, generate_block_package
from django.conf import settings
from urllib.parse import unquote
from html2docx import html2docx

# para pruebas de pdf
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# Definir tamaño carta (Letter)
LETTER = (612, 792)  # 21,59cm x 27,94cm

def generar_certificado(request, user_id, contrato_id):
    # =============================
    # 1) Obtener datos
    # =============================
    usuario = get_object_or_404(CustomUser, id=user_id)
    contrato = get_object_or_404(Contrato, id=contrato_id, usuario=usuario)

    # =============================
    # 2) Registrar fuentes Calibri
    # =============================
    ruta_fuente = os.path.join(settings.BASE_DIR, "static", "fonts")
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(ruta_fuente, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(ruta_fuente, "calibrib.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Italic", os.path.join(ruta_fuente, "calibrii.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-BoldItalic", os.path.join(ruta_fuente, "calibriz.ttf")))

    # =============================
    # 3) Variables de contenido
    # =============================
    tituloInicial = "<b>EL SUSCRITO SUBDIRECTOR (E) DEL SERVICIO NACIONAL DE APRENDIZAJE SENA</b>"
    introduccion = f"""Que el (la) señor(a) {usuario.nombres} {usuario.apellidos} identificado(a) con 
    {usuario.tipo_documento} No. {usuario.numero_documento} de Popayán celebró con EL SERVICIO NACIONAL DE APRENDIZAJE SENA, 
    el (los) siguiente(s) contrato(s) de prestación de servicios personales regulados por la Ley 80 de 1993, 
    Ley 1150 de 2007 y Decreto 1082 de 2015, como se describe a continuación:"""

    # =============================
    # 4) Documento base
    # =============================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="certificado_{contrato.numero_contrato}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=LETTER,
                            leftMargin=3*cm, rightMargin=3*cm,
                            topMargin=3*cm, bottomMargin=2.5*cm)

    # =============================
    # 5) Estilos
    # =============================
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SubtituloCalibri",
        fontName="Calibri-Bold",
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        leading=21  # 1.5 * 14
    ))
    styles.add(ParagraphStyle(
        name="IntroCalibri",
        fontName="Calibri",
        fontSize=11,
        alignment=TA_JUSTIFY,
        leading=16.5  # 1.5 * 11
    ))
    styles.add(ParagraphStyle(
        name="TablaTitulo",
        fontName="Calibri-Bold",
        fontSize=11,
        alignment=TA_LEFT,
        spaceAfter=3,
        leading=16.5  # 1.5 * 11
    ))
    styles.add(ParagraphStyle(
        name="TablaTexto",
        fontName="Calibri",
        fontSize=11,
        alignment=TA_JUSTIFY,
        leading=16.5  # 1.5 * 11
    ))
    styles.add(ParagraphStyle(
        name="FirmaPrincipal",
        fontName="Calibri",
        fontSize=11,
        alignment=TA_LEFT,
        leading=16.5  # 1.5 * 11
    ))
    styles.add(ParagraphStyle(
        name="FirmaSecundaria",
        fontName="Calibri",
        fontSize=10,
        alignment=TA_LEFT,
        leading=15  # 1.5 * 10
    ))

    elementos = []

    # ---------------- SUBTÍTULOS ----------------
    elementos.append(Paragraph(tituloInicial, styles["SubtituloCalibri"]))
    elementos.append(Paragraph("<b>HACE CONSTAR</b>", styles["SubtituloCalibri"]))
    elementos.append(Spacer(1, 15))

    # ---------------- INTRO ----------------
    elementos.append(Paragraph(introduccion, styles["IntroCalibri"]))
    elementos.append(Spacer(1, 15))

    # ---------------- TABLA DE DATOS ----------------
    data = [
        [Paragraph("Número y Fecha del Contrato:", styles["TablaTitulo"]),
         Paragraph(f"{contrato.numero_contrato} del {contrato.fecha_inicio}", styles["TablaTexto"])],
        [Paragraph("Objeto:", styles["TablaTitulo"]),
         Paragraph(contrato.objeto or "N/A", styles["TablaTexto"])],
        [Paragraph("Plazo de ejecución:", styles["TablaTitulo"]),
         Paragraph(f"Del {contrato.fecha_inicio} al {contrato.fecha_fin}", styles["TablaTexto"])],
        [Paragraph("Valor:", styles["TablaTitulo"]),
         Paragraph(f"El valor del contrato para todos los efectos legales y fiscales, se fijó en la suma de ${contrato.valor_pago}(cuantía del contrato)".replace(",", "."), styles["TablaTexto"])],
        [Paragraph("Obligaciones Específicas:", styles["TablaTitulo"]),
         Paragraph(contrato.objetivos_especificos or "N/A", styles["TablaTexto"])]
    ]
    tabla = Table(data, colWidths=[6*cm, (LETTER[0] - 6*cm - 6*cm)])
    tabla.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 15))

    # ---------------- EXPEDICIÓN ----------------
    expedicion = """Se expide a solicitud del interesado(a), de acuerdo con la información registrada en los sistemas de información con los que cuenta el SENA, a los diez (10) días de febrero de 2025."""
    elementos.append(Paragraph(expedicion, styles["IntroCalibri"]))
    elementos.append(Spacer(1, 30))

    # ---------------- FIRMAS ----------------
    firma_subdirector = Paragraph(
    """<br/><b>Firma</b><br/>
    <b>DARIO BERNARDO MONTUFAR BLANCO</b><br/>
    Subdirector (E) del Centro Agropecuario<br/>
    <b>Servicio Nacional de Aprendizaje SENA</b>""",
    styles["FirmaPrincipal"]
    )
    firma_proyecto = Paragraph(
        """Proyecto: Danna Isabela Ordoñez Navia<br/>
        Cargo: Apoyo Financiero y Administrativo Grupo Intercentros""",
        styles["FirmaSecundaria"]
    )
    firma_reviso = Paragraph(
        """Revisó: Ariel Pabón<br/>
        Cargo: Coordinador Administrativo y Financiero Intercentros""",
        styles["FirmaSecundaria"]
    )

    tabla_firmas = Table(
    [[firma_subdirector, None],
     [Spacer(1, 40), None],
     [firma_proyecto, None],
     [Spacer(1, 20), None],
     [firma_reviso, None]],
    colWidths=[LETTER[0] / 2 - 2*cm, LETTER[0] / 2 - 2*cm]
    )
    tabla_firmas.setStyle(TableStyle([
    ("ALIGN", (0,0), (0,0), "LEFT"),     # Proyecto y Reviso alineados a la izquierda
    ("ALIGN", (1,0), (1,0), "RIGHT"),    # Subdirector alineado a la derecha
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 0),
    ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    elementos.append(Spacer(1, 40))
    elementos.append(tabla_firmas)

    # ---------------- ENCABEZADO Y PIE ----------------
    def header_footer(canvas, doc):
        canvas.saveState()
        ruta_logo = os.path.join(settings.BASE_DIR, "static", "img", "logo-sena-verde.jpg")
        logo = ImageReader(ruta_logo)
        canvas.drawImage(logo, LETTER[0]/2 - 25, LETTER[1]-70,
                         width=50, height=50, preserveAspectRatio=True)

        canvas.setFont("Calibri-Italic", 11)
        canvas.drawString(3*cm, LETTER[1]-70, f"Certificación No. {contrato.id:03d}")

        footer_text = "Regional Cauca / Centro de Formación Agropecuario - Carrera 9ª 71N–60 B/ El Placer, Popayán – Cauca. PBX 57 602 8247678 Ext:2224"
        canvas.setFillColorRGB(0, 0.5, 0)  # verde SENA
        canvas.setFont("Calibri", 9)
        canvas.drawCentredString(LETTER[0] / 2.0, 1.56*cm, footer_text)
        canvas.setFillColorRGB(0, 0, 0)  # restaurar negro para lo demás

    # ---------------- RENDER ----------------
    doc.build(elementos, onFirstPage=header_footer, onLaterPages=header_footer)
    return response

# Create your views here.
@login_required
def upload_pdf_view(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)

    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf = request.FILES["pdf_file"]
        data = extract_key_value_from_pdf(pdf)

        # Limpiar datos anteriores
        TempExtractedData.objects.filter(usuario=usuario).delete()

        # Guardar secciones extraídas
        for item in data:
            TempExtractedData.objects.create(
                usuario=usuario,
                clave=item["clave"],  # ej: "1.", "2°"
                valor=item["valor"]   # todo el texto del bloque
            )

        messages.success(request, "✅ PDF procesado por secciones.")
        return redirect("documents:select_data", user_id=usuario.id)

    return render(request, "documents/upload_pdf.html", {"usuario": usuario})


@login_required
def select_data_view(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)
    temp_data = TempExtractedData.objects.filter(usuario=usuario)

    if request.method == "POST":
        seleccionados = request.POST.getlist("selected")
        numero_contrato = request.POST.get("numero_contrato")  # manual
        contratista = request.POST.get("contratista")  # manual

        for item in temp_data:
            if str(item.id) in seleccionados:
                UserContractData.objects.update_or_create(
                    usuario=usuario,
                    campo=item.clave,
                    defaults={"valor": item.valor}
                )

        # Guardar manuales directamente en la tabla final
        if numero_contrato:
            UserContractData.objects.update_or_create(
                usuario=usuario, campo="Número de Contrato", defaults={"valor": numero_contrato}
            )
        if contratista:
            UserContractData.objects.update_or_create(
                usuario=usuario, campo="Contratista", defaults={"valor": contratista}
            )

        temp_data.delete()
        messages.success(request, "Datos guardados en la tabla final con los campos manuales incluidos.")
        return redirect("certificates:manual_fields", user_id=usuario.id)

    return render(
        request,
        "documents/select_data.html",
        {"temp_data": temp_data, "usuario": usuario}
    )

@login_required
@require_POST
def contrato_create_modal(request):
    usuario_id = request.POST.get("usuario_id")
    contrato_id = request.POST.get("contrato_id")  # 👈 ahora puede llegar en el form
    usuario = get_object_or_404(CustomUser, id=usuario_id)

    instance = None
    if contrato_id:
        instance = get_object_or_404(Contrato, id=contrato_id, usuario=usuario)

    form = ContratoModalForm(request.POST, request.FILES, instance=instance, initial={"usuario": usuario})
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    archivo = request.FILES.get("archivo")
    try:
        if archivo:
            file_bytes = archivo.read()
            metadata = extract_contract_metadata(BytesIO(file_bytes))
        else:
            file_bytes = None
            metadata = {}

        contrato = form.save(commit=False)
        contrato.usuario = usuario

        # Completar con metadatos del PDF si no están en el form
        contrato.objetivos_especificos = contrato.objetivos_especificos or metadata.get("objetivos_especificos", "")
        contrato.valor_pago = contrato.valor_pago or metadata.get("valor_pago", "")
        contrato.objeto = contrato.objeto or metadata.get("objeto", "")
        contrato.fecha_fin = contrato.fecha_fin or metadata.get("plazo_fecha", "")

        if not contrato.numero_contrato:
            return JsonResponse({"ok": False, "errors": {"numero_contrato": ["Número de contrato requerido."]}}, status=400)

        contrato.save()

        # Si hay archivo, reemplazarlo
        if file_bytes:
            contrato.archivo.save(f"{contrato.numero_contrato}.pdf", ContentFile(file_bytes), save=True)

        # Actualizar tabla
        html_table = render_to_string(
            "documents/partials/contratos_table.html",
            {"contratos": usuario.contratos.order_by('-creado')},
            request=request
        )

        return JsonResponse({
            "ok": True,
            "message": "Contrato guardado correctamente.",
            "table_html": html_table
        })

    except Exception as e:
        return JsonResponse({"ok": False, "errors": {"__all__": [str(e)]}}, status=500)

@csrf_exempt
@require_POST
def prefill_contrato(request):
    try:
        archivo = request.FILES.get("archivo")
        if not archivo:
            return JsonResponse({"ok": False, "error": "No se envió ningún archivo."}, status=400)

        metadata = extract_contract_metadata(archivo)
        return JsonResponse({"ok": True, "metadata": metadata})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@login_required
def contratos_usuario_view(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)
    contratos = usuario.contratos.all()

    html = render_to_string(
        "documents/partials/contratos_table.html",
        {"contratos": contratos},
        request=request
    )

    return JsonResponse({"html": html})

# editable contrato
@login_required
def contrato_detail(request, contrato_id):
    contrato = get_object_or_404(Contrato, id=contrato_id)

    try:
        data = {
            "id": contrato.id,
            "numero_contrato": contrato.numero_contrato or "",
            "fecha_inicio": contrato.fecha_inicio or "",
            "fecha_generacion": contrato.fecha_generacion or "",
            "fecha_fin": contrato.fecha_fin or "",
            "valor_pago": contrato.valor_pago or "",
            "objeto": contrato.objeto or "",
            "objetivos_especificos": contrato.objetivos_especificos or "",
        }
        return JsonResponse({"ok": True, "contrato": data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# Crear certificado individual
@login_required
@require_POST
def generate_individual_documents(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    selected = request.POST.get("selected_ids", "")
    contratos_qs = Contrato.objects.filter(usuario=usuario)

    if selected:
        ids = [int(x) for x in selected.split(",") if x.strip().isdigit()]
        contratos_qs = contratos_qs.filter(id__in=ids)

    if not contratos_qs.exists():
        return JsonResponse({"ok": False, "error": "No se encontraron contratos"}, status=400)

    template_path = os.path.join(
        settings.BASE_DIR, "templates", "base", "boceto para pruebas.docx"
    )
    if not os.path.isfile(template_path):
        return JsonResponse({"ok": False, "error": "Plantilla no encontrada"}, status=500)

    try:
        generated_files = []
        for contrato in contratos_qs:
            file_path = generate_individual_docx(usuario, contrato, template_path)
            generated_files.append(os.path.basename(file_path))

        return JsonResponse({
            "ok": True,
            "files": generated_files,
            "message": f"{len(generated_files)} certificados generados correctamente"
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
    
# crear certificado por bloques
@login_required
@require_POST
def generate_block_documents(request, user_id):
    """
    Genera todos los contratos seleccionados en BLOQUE (un único .docx),
    empaca con el Excel y devuelve un ZIP.
    """
    usuario = get_object_or_404(CustomUser, id=user_id)

    selected = request.POST.get("selected_ids", "")
    contratos_qs = Contrato.objects.filter(usuario=usuario)
    if selected:
        ids = [int(x) for x in selected.split(",") if x.strip().isdigit()]
        contratos_qs = contratos_qs.filter(id__in=ids)

    if not contratos_qs.exists():
        return JsonResponse({"ok": False, "error": "No se encontraron contratos para generar."}, status=400)

    template_path = os.path.join(settings.BASE_DIR, "templates", "base", "boceto para pruebas.docx")
    if not os.path.isfile(template_path):
        return JsonResponse({"ok": False, "error": "Plantilla boceto no encontrada en templates/base/."}, status=500)

    try:
        zip_path = generate_block_package(usuario, contratos_qs, template_path)
        return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=os.path.basename(zip_path))
    except Exception as e:
        # registra/loguea si tienes logger
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@login_required
def listar_docx_guardados(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)

    # 🔹 Reglas de acceso
    if request.user.id != usuario.id:
        if not (request.user.role and request.user.role.nombre in ["Administrador", "Funcionario"]):
            return JsonResponse({"ok": False, "error": "No autorizado"}, status=403)

    folder_individual = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "individual")
    folder_bloques = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "bloques")
    files = []
    for folder in [folder_individual, folder_bloques]:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower().endswith(".docx"):
                    files.append({"name": f})

    return JsonResponse({"ok": True, "files": files})

#  esto es para dar acceso a cualquier usuario autorizado (admin, funcionario)
def _can_access_user(request_user, target_user):
    if request_user.id == target_user.id:
        return True
    if getattr(request_user, "role", None) and request_user.role.nombre in ["Administrador", "Funcionario"]:
        return True
    return False

# Vista para previsualizar .docx
@require_GET
def preview_docx(request, user_id, filename):
    usuario = get_object_or_404(CustomUser, id=user_id)
    folder = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "individual")
    path = os.path.join(folder, filename)

    if not os.path.isfile(path):
        raise Http404("Archivo no encontrado")

    return FileResponse(open(path, "rb"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# Descargar y eliminar el archivo
@login_required
@require_GET
def download_and_delete_docx(request, user_id, filename):
    usuario = get_object_or_404(CustomUser, id=user_id)
    file_path = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "individual", filename)
    if not os.path.isfile(file_path):
        return HttpResponse("Archivo no encontrado", status=404)

    response = FileResponse(open(file_path, "rb"), as_attachment=True, filename=filename)

    def cleanup_file(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error eliminando {path}: {e}")

    from threading import Timer
    Timer(5.0, cleanup_file, args=[file_path]).start()
    return response

# Subir el nuevo archivo editado y regenerar ZIP
@require_POST
def upload_edited_docx(request, user_id):
    usuario = get_object_or_404(CustomUser, id=user_id)
    folder = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "individual")
    os.makedirs(folder, exist_ok=True)

    file = request.FILES.get("archivo")
    if not file:
        return JsonResponse({"ok": False, "error": "No se envió archivo"}, status=400)

    save_path = os.path.join(folder, file.name)
    with open(save_path, "wb+") as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    # regenerar ZIP si existe bloque
    bloque_folder = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "bloques")
    zip_path = os.path.join(bloque_folder, f"contratos_bloque_{usuario.numero_documento}.zip")
    if os.path.exists(bloque_folder):
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in os.listdir(bloque_folder):
                if f.endswith(".docx") or f.endswith(".xlsx"):
                    zf.write(os.path.join(bloque_folder, f), arcname=f)

    return JsonResponse({"ok": True, "file": file.name, "message": "Documento actualizado y ZIP regenerado"})


