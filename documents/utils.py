import os 
import tempfile
import shutil
import zipfile
import pdfplumber
import unicodedata
import re
import pandas as pd

from django.conf import settings
from mailmerge import MailMerge
from django.utils.text import slugify
from datetime import date
from io import BytesIO
from docx import Document

SPANISH_MONTHS = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,
    "noviembre":11,"diciembre":12
}

def _parse_spanish_date(text):
    if not text:
        return None
    t = text.strip().lower()
    m = re.search(r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})', t, re.I)
    if m:
        try:
            return date(int(m.group(3)), SPANISH_MONTHS[m.group(2)], int(m.group(1)))
        except:
            return None
    m2 = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})', t)
    if m2:
        y = int(m2.group(3))
        if y < 100: y += 2000
        try:
            return date(y, int(m2.group(2)), int(m2.group(1)))
        except:
            return None
    return None

def _extract_value_amount(text):
    if not text:
        return None
    m = re.search(r'\$\s*[\d\.,]+', text)
    if m:
        return m.group(0).strip()
    m2 = re.search(r'\(\s*\$?\s*[\d\.,]+\s*\)', text)
    if m2:
        return m2.group(0).strip("()").strip()
    return None

def _amount_to_digits(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[^\d]', '', text) or ""

def _format_amount(valor_num: str) -> str:
    """Formatea con puntos de miles: 2472000 -> 2.472.000"""
    try:
        n = int(valor_num)
        return f"{n:,}".replace(",", ".")
    except:
        return valor_num

def _clean_plazo_text(text):
    """Extrae y devuelve la fecha del plazo tal cual como texto (sin convertir a date)."""
    if not text:
        return ""
    m = re.search(r"\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+\d{4}", text, re.I)
    if m:
        return m.group(0).strip()
    return text.strip()

def _normalize_objeto(text):
    """
    Limpia y organiza el texto del OBJETO:
    - Separa por puntos, punto y coma o frases clave en mayúscula
    - Convierte a párrafos legibles
    """
    if not text:
        return ""
    # Normalizar saltos
    s = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Quitar espacios múltiples
    s = re.sub(r'\s+', ' ', s)

    # Forzar salto de línea en separadores comunes
    s = re.sub(r'(\.)(\s+)', r'\1\n', s)          # después de puntos
    s = re.sub(r'(;)(\s+)', r'\1\n', s)           # después de ;
    s = re.sub(r'\s+(EDUCACI[oÓ]N|EXPERIENCIA|FORMACI[oÓ]N)\s+', r'\n\1 ', s, flags=re.I)

    # Limpiar espacios al inicio de cada línea
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines)

def _extract_objeto(texto):
    """
    Extrae el OBJETO con formato parecido al de las obligaciones.
    Intenta separar por frases largas o numeraciones.
    """
    if not texto:
        return ""

    # Compactar espacios y saltos
    s = re.sub(r'\s+', ' ', texto).strip()

    # Forzar saltos después de ; o .
    s = re.sub(r'([.;:])\s+', r'\1\n', s)

    # Saltos antes de palabras clave
    s = re.sub(r'\s+(EDUCACI[oÓ]N|FORMACI[oÓ]N|EXPERIENCIA)\s+', r'\n\1 ', s, flags=re.I)

    # Quitar espacios basura en cada línea
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines)

def extract_key_value_from_pdf(pdf_file):
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)

        # ===== OBJETO =====
        match_objeto = re.search(
            r"OBJETO[:\s]*(.*?)(EDUCACI[oÓ]N\s+Y/O\s+FORMACI[oÓ]N|VALOR|PLAZO|$)",
            full_text, re.I | re.S
        )
        if match_objeto:
            objeto_text = _extract_objeto(match_objeto.group(1))
            out.append({"clave": "Objeto", "valor": objeto_text})

        # ===== VALOR =====
        match_valor = re.search(
            r"VALOR\s+Y\s+FORMA\s+DE\s+PAGO[:\s]*(.*?)(PLAZO|LUGAR|SUPERVISOR|$)",
            full_text, re.I | re.S
        )
        if match_valor:
            valor_text = match_valor.group(1).strip()
            valor_num = _amount_to_digits(_extract_value_amount(valor_text) or valor_text)
            if valor_num:
                valor_fmt = f"{int(valor_num):,}".replace(",", ".")
                out.append({"clave": "Valor de Pago", "valor": valor_fmt})

        # ===== PLAZO =====
        match_plazo = re.search(
            r"PLAZO[:\s]*(.*?)(LUGAR|SUPERVISOR|ORDENADOR|$)",
            full_text, re.I | re.S
        )
        if match_plazo:
            plazo_text = _clean_plazo_text(match_plazo.group(1))
            if plazo_text:
                out.append({"clave": "Plazo", "valor": plazo_text})

        # ===== OBJETIVOS ESPECÍFICOS =====
        match_objetivos = re.search(
            r"(OBJETIVOS\s+ESPEC[IÍ]FICOS|OBLIGACIONES\s+ESPEC[IÍ]FICAS)[:\s]*(.*?)(PAR[ÁA]GRAFO|OBLIGACIONES\s+DEL|IDENTIFICACI[oó]N|$)",
            full_text, re.S | re.I
        )
        if match_objetivos:
            objetivos_text = " ".join(match_objetivos.group(2).split())
            out.append({"clave": "Objetivos Específicos", "valor": objetivos_text})

    return out


def extract_contract_metadata(pdf_file):
    items = extract_key_value_from_pdf(pdf_file)

    metadata = {
        "objeto": "",
        "valor_pago": "",
        "plazo_fecha": "",
        "objetivos_especificos": "",
    }

    for it in items:
        k = (it["clave"] or "").lower()
        if "objeto" in k:
            metadata["objeto"] = it["valor"]
        elif "valor" in k:
            metadata["valor_pago"] = it["valor"]
        elif "plazo" in k:
            metadata["plazo_fecha"] = it["valor"]
        elif "objetivo" in k:
            metadata["objetivos_especificos"] = it["valor"]

    return metadata

#prueba de mailmerge
def _safe_filename(s: str) -> str:
    if not s:
        return "sin_numero"
    return slugify(s)[:120]

def _clean_multiline_text(raw):
    """
    Convierte texto en varias líneas (separadas por \n) que Word MailMerge puede
    mostrar en lista si el campo tiene formato de lista en el docx.
    """
    if not raw:
        return ""
    s = str(raw).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in s.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

def _format_as_singleline(raw):
    """
    Convierte texto multilínea en una sola línea corrida,
    respetando el formato de párrafo justificado en Word.
    """
    if not raw:
        return ""
    s = str(raw).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # Colapsar espacios múltiples
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def generate_individual_docx(usuario, contrato, template_docx_path):
    """
    Genera un único DOCX para un contrato específico
    y lo guarda en la carpeta media/usuarios/<documento>/individual/.
    Devuelve la ruta del archivo generado.
    """
    base_folder = os.path.join(
        settings.MEDIA_ROOT, "usuarios", usuario.numero_documento, "individual"
    )
    os.makedirs(base_folder, exist_ok=True)

    nro = contrato.numero_contrato or f"id{contrato.id}"
    out_name = f"{_safe_filename(nro)}.docx"
    out_path = os.path.join(base_folder, out_name)

    try:
        with MailMerge(template_docx_path) as m:
            row = {
                "NUMERO_CONTRATO": contrato.numero_contrato or "",
                "FECHA_GENERACION": str(contrato.fecha_generacion or "").strip(),
                "FECHA_INICIO": str(contrato.fecha_inicio or "").strip(),
                "FECHA_FINAL": str(contrato.fecha_fin or "").strip(),
                "VALOR_PAGO": str(contrato.valor_pago or "").strip(),
                "OBJETO": _clean_multiline_text(contrato.objeto),
                "OBJETIVOS_ESPECIFICOS": _clean_multiline_text(contrato.objetivos_especificos),
                "NOMBRE_COMPLETO": f"{usuario.nombres or ''} {usuario.apellidos or ''}".strip(),
                "TIPO_DOCUMENTO": usuario.get_tipo_documento_display_full(),
                "NUMERO_DOCUMENTO": usuario.numero_documento or "",
                "EMAIL": usuario.email or "",
            }
            m.merge(**row)
            m.write(out_path)
    except Exception as e:
        # fallback: guardar copia vacía
        shutil.copy(template_docx_path, out_path)
        print("Error generando DOCX:", e)

    return out_path

# generacion de certificado por bloques 

def _safe_filename(name: str) -> str:
    """Convierte un string a un nombre de archivo seguro."""
    if not name:
        return "sin_numero"
    name = str(name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s\-]", "", name).strip()
    name = re.sub(r"[\s]+", "_", name)
    return name[:180]

def _clean_multiline_text(text: str) -> str:
    """Limpia saltos de línea repetidos y normaliza texto para docx."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # quita dobles saltos
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def _format_as_singleline(text: str) -> str:
    """Convierte texto multilínea a una sola línea (útil para Excel)."""
    if not text:
        return ""
    return " ".join(_clean_multiline_text(text).splitlines())

def generate_block_package(usuario, contratos_qs, template_docx_path):
    """
    Genera:
      - Un único Word (contratos_bloque.docx) con todos los contratos concatenados (sin saltos de página adicionales)
      - Un Excel de control (contratos.xlsx)
      - Empaqueta ambos en un ZIP y devuelve la ruta absoluta del ZIP
    """
    if not contratos_qs.exists():
        raise ValueError("No hay contratos para generar.")

    # carpeta destino: media/usuarios/<documento>/bloques/
    base_folder = os.path.join(settings.MEDIA_ROOT, "usuarios", usuario.numero_documento or "sin_documento", "bloques")
    os.makedirs(base_folder, exist_ok=True)

    temp_dir = tempfile.mkdtemp()

    try:
        # --- Generar Excel de control ---
        rows = []
        for c in contratos_qs:
            rows.append({
                "NUMERO_CONTRATO": c.numero_contrato or "",
                "FECHA_GENERACION": str(c.fecha_generacion or "").strip(),
                "FECHA_INICIO": str(c.fecha_inicio or "").strip(),
                "FECHA_FINAL": str(c.fecha_fin or "").strip(),
                "VALOR_PAGO": str(c.valor_pago or "").strip(),
                "OBJETO": _format_as_singleline(c.objeto),
                "OBJETIVOS_ESPECIFICOS": _clean_multiline_text(c.objetivos_especificos),
                "CONTRATO_ID": c.id,
                "NOMBRE_COMPLETO": f"{getattr(usuario, 'nombres', '') or ''} {getattr(usuario, 'apellidos', '') or ''}".strip(),
                "TIPO_DOCUMENTO": getattr(usuario, "get_tipo_documento_display_full", lambda: "")(),
                "NUMERO_DOCUMENTO": usuario.numero_documento or "",
                "EMAIL": usuario.email or "",
            })

        df = pd.DataFrame(rows)
        excel_path = os.path.join(temp_dir, "contratos.xlsx")
        df.to_excel(excel_path, index=False, engine="openpyxl")

        # --- Generar DOCX individuales (temporales) con MailMerge ---
        temp_docs = []
        for row, contrato in zip(rows, contratos_qs):
            nro = row.get("NUMERO_CONTRATO") or f"id{row.get('CONTRATO_ID')}"
            out_path = os.path.join(temp_dir, f"{_safe_filename(nro)}.docx")

            with MailMerge(template_docx_path) as m:
                # los campos que van al merge
                safe_row = {k: (v if v is not None else "") for k, v in row.items()}
                safe_row.pop("CONTRATO_ID", None)
                # para el campo OBJETO preferimos mantener saltos (alineado con plantilla)
                safe_row["OBJETO"] = _clean_multiline_text(getattr(contrato, "objeto", ""))

                m.merge(**safe_row)
                m.write(out_path)

            temp_docs.append(out_path)

        # --- Concatenar todos los .docx en uno solo (manteniendo estilo de plantilla) ---
        # Usamos el primer doc como "master"
        master_doc = Document(temp_docs[0])

        # Append elements from subsequent docs to master.body
        for extra_doc_path in temp_docs[1:]:
            subdoc = Document(extra_doc_path)
            for element in subdoc.element.body:
                master_doc.element.body.append(element)

        bloque_path = os.path.join(temp_dir, "contratos_bloque.docx")
        master_doc.save(bloque_path)

        # --- Crear ZIP con el Excel y el docx bloque ---
        zip_name = f"contratos_bloque_{usuario.numero_documento or 'sin_documento'}.zip"
        zip_path = os.path.join(base_folder, zip_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(excel_path, arcname="contratos.xlsx")
            zf.write(bloque_path, arcname="contratos_bloque.docx")
            
        # copia el docx del bloque al folder del usuario 
        try:
            shutil.copy(bloque_path, os.path.join(base_folder, "contratos_bloque.docx"))
        except Exception as e:
            print("Error al copiar docx bloque:", e)

        return zip_path

    finally:
        # limpiar temporales
        shutil.rmtree(temp_dir, ignore_errors=True)