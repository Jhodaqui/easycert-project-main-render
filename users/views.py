from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .utils import crear_carpetas as crear_CarpetasUsuario
from django.template.loader import render_to_string
from django.http import JsonResponse, HttpResponse


from .forms import RegisterForm, LoginForm, ConstanciaForm, BulkUploadForm, MunicipiosUploadForm
import io
import csv
import pandas as pd
from .models import CustomUser, Constancia, municipios, dptos, Rol
from datetime import date

# correo 
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import threading
import logging

logger = logging.getLogger(__name__)

# Create your views here.

# Registro
def send_email_async(msg):
    """Envía correo en un hilo aparte para no bloquear el registro."""
    try:
        msg.send()
        logger.info("Correo enviado correctamente en background.")
    except Exception as e:
        logger.error(f"Error enviando correo de bienvenida: {e}")

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()

            crear_CarpetasUsuario(user)  # se mantiene

            # --- preparar correo ---
            subject = "Bienvenido al sistema de certificaciones"
            from_email = settings.EMAIL_HOST_USER
            to_email = [user.email]

            text_content = f"Hola {user.nombres}, tu registro fue exitoso."
            html_content = f"""
                <p>Hola <strong>{user.nombres}</strong>,</p>
                <p>Tu registro en el sistema de certificaciones fue exitoso.</p>
                <p>Ya puedes iniciar sesión con tu correo y contraseña.</p>
            """

            msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
            msg.attach_alternative(html_content, "text/html")

            # 🚀 Envío asíncrono
            threading.Thread(target=send_email_async, args=(msg,), daemon=True).start()

            messages.success(request, "Usuario registrado con éxito. Se envió un correo de bienvenida.")
            return redirect("login")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = RegisterForm()

    return render(request, "users/register.html", {"form": form})

# =========================
# AJAX: cargar centros por depto
# =========================
def cargar_centros(request):
    depto_id = request.GET.get("departamento")
    centros = municipios.objects.filter(idDepto_id=depto_id).values("idMpio", "nombreCentro")
    return JsonResponse(list(centros), safe=False)

# fin del correo

# Login
def login_view(request):
    form = LoginForm(request.POST or None)
    field_errors = {}

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)

                    # 🔹 Redirección según el nombre del rol
                    if user.role and user.role.nombre == "Administrador":
                        return redirect("admin_dashboard")
                    elif user.role and user.role.nombre == "Funcionario":
                        return redirect("staff_dashboard")
                    else:
                        return redirect("user_dashboard")
                else:
                    field_errors['general'] = "⏳ Tu cuenta aún no está activada."
            else:
                field_errors['general'] = "🔒 Correo electrónico o contraseña incorrectos."
        else:
            for field, errors in form.errors.items():
                field_errors[field] = " ".join(errors)

    return render(request, "users/login.html", {
        "form": form,
        "field_errors": field_errors
    })

# Logout
def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión.")
    return redirect("login")


# Home (dashboard simple)
@login_required
def home_view(request):
    return render(request, "home.html")


# Password reset request
def password_reset_request_view(request):
    from .forms import PasswordResetRequestForm
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            user = CustomUser.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = request.build_absolute_uri(f"/users/reset/{uid}/{token}/")
            subject = "Restablecer contraseña EasyCert"
            message = render_to_string("users/emails/password_reset_email.html", {"user": user, "reset_link": reset_link})
            send_mail(
                subject,
                "Versión de texto plano: copia y pega este enlace para restablecer tu contraseña: " + reset_link,  # respaldo en texto
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
                html_message=message  # 👈 clave para que el correo se vea con estilos
            )
            messages.success(request, "Se envió un enlace para restablecer la contraseña.")
            return redirect("login")
    else:
        form = PasswordResetRequestForm()
    return render(request, "users/password_reset_request.html", {"form": form})


# Password reset confirm
from django.contrib.auth.hashers import make_password
def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            p1 = request.POST.get("password1")
            p2 = request.POST.get("password2")
            if p1 != p2:
                messages.error(request, "Las contraseñas no coinciden.")
            elif len(p1) < 4:  # regla mínima relajada
                messages.error(request, "La contraseña debe tener al menos 4 caracteres.")
            else:
                user.set_password(p1)
                user.save()
                messages.success(request, "Contraseña cambiada correctamente. Ya puedes iniciar sesión.")
                return redirect("login")
        return render(request, "users/password_reset_confirm.html", {"validlink": True})
    messages.error(request, "El enlace no es válido o ha expirado.")
    return redirect("password_reset")

# vistas segun roles
@login_required
def admin_dashboard(request):
    return render(request, "users/admin/dashboard.html")

def datos_bulk_upload(request):
    if request.method == "POST":
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES["file"]
            file_name = file.name.lower()

            try:
                # 📌 Leer CSV
                if file_name.endswith(".csv"):
                    decoded_file = file.read().decode("utf-8")
                    io_string = io.StringIO(decoded_file)
                    reader = csv.DictReader(io_string)
                    rows = list(reader)

                # 📌 Leer Excel
                elif file_name.endswith(".xls") or file_name.endswith(".xlsx"):
                    df = pd.read_excel(file)
                    rows = df.to_dict(orient="records")

                else:
                    messages.error(request, "Formato no soportado. Solo CSV o Excel.")
                    return redirect("datos_bulk_upload")

                if not rows:
                    messages.error(request, "El archivo está vacío.")
                    return redirect("datos_bulk_upload")

                # Normalizamos encabezados a minúsculas
                headers = [h.lower() for h in rows[0].keys()]

                # ==============================
                # 📌 Carga de Usuarios
                # ==============================
                if {"nombres", "apellidos", "tipo_documento", "numero_documento", "email"}.issubset(headers):
                    for row in rows:
                        data = {
                            "nombres": row.get("nombres"),
                            "apellidos": row.get("apellidos"),
                            "tipo_documento": row.get("tipo_documento"),
                            "numero_documento": row.get("numero_documento"),
                            "email": row.get("email"),
                            "password1": row.get("password") or "12345",
                            "password2": row.get("password") or "12345",
                        }

                        user_form = RegisterForm(data)
                        if user_form.is_valid():
                            user = user_form.save()
                            crear_CarpetasUsuario(user)
                        else:
                            messages.error(request, f"Error en {row.get('email')}: {user_form.errors}")

                    messages.success(request, "Usuarios cargados correctamente.")

                # ==============================
                # 📌 Carga de Municipios
                # ==============================
                elif {"nombrempio", "iddepto", "nombrecentro"}.issubset(headers):
                    for row in rows:
                        nombre_mpio = row.get("nombreMpio") or row.get("nombrempio")
                        id_depto = row.get("idDepto") or row.get("iddepto")
                        nombre_centro = row.get("nombreCentro") or row.get("nombrecentro") or None

                        # Verificar si el departamento existe
                        try:
                            depto = dptos.objects.get(idDepto=id_depto)
                        except dptos.DoesNotExist:
                            messages.error(
                                request,
                                f"Departamento con ID {id_depto} no existe. Línea omitida: {nombre_mpio}"
                            )
                            continue

                        # Crear el municipio
                        municipios.objects.create(
                            nombreMpio=nombre_mpio,
                            idDepto=depto,
                            nombreCentro=nombre_centro
                        )

                    messages.success(request, "Municipios cargados correctamente.")

                else:
                    messages.error(request, "El archivo no tiene un formato válido para usuarios o municipios.")
                    return redirect("datos_bulk_upload")

                return redirect("datos_bulk_upload")

            except Exception as e:
                messages.error(request, f"Ocurrió un error procesando el archivo: {str(e)}")
                return redirect("datos_bulk_upload")

    else:
        form = BulkUploadForm()

    # ==============================
    # 📌 Mostrar datos existentes
    # ==============================
    User = get_user_model()
    users = User.objects.exclude(role_id="1")  # Ocultar admins
    mpio = municipios.objects.select_related("idDepto").all()

    return render(request, "users/admin/datos_bulk_upload.html", {
        "form": form,
        "users": users,
        "municipios": mpio,
    })

@login_required
def staff_dashboard(request):
    # Aquí puedes filtrar según permisos/rol
    solicitudes = Constancia.objects.all().order_by("creado_en")
    usuario = CustomUser.objects.get(id=request.user.id)

    return render(request, "users/staff/dashboard.html", {"solicitudes": solicitudes, "usuario": usuario})

@login_required
def user_dashboard(request):
    user = request.user  
    
    solicitudes = Constancia.objects.filter(usuario=user).order_by("-creado_en")

    return render(
        request,
        "users/user/dashboard_home.html",
        {"solicitudes": solicitudes}
    )

@login_required
def mostrar_formulario_constancia(request):
    user = request.user

    initial_data = {
        "nombre_completo": f"{user.nombres} {user.apellidos}",
        "numero_documento": user.numero_documento,
        "tipo_documento": user.tipo_documento,
        "email": user.email,
    }

    form = ConstanciaForm(initial=initial_data)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            "users/partials/form_constancia_partial.html",
            {"form": form},
            request=request
        )
        return JsonResponse({"form_html": html})

    return JsonResponse({"error": "Petición inválida"}, status=400)

@login_required
def procesar_constancia(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        user = request.user
        
        initial_data = {
            "nombre_completo": f"{user.nombres} {user.apellidos}",
            "numero_documento": user.numero_documento,
            "tipo_documento": user.tipo_documento,
            "email": user.email,
        }

        form = ConstanciaForm(request.POST, initial=initial_data)
        
        if form.is_valid():
            try:
                Constancia.objects.create(
                    usuario=user,
                    fecha_inicial=date(int(form.cleaned_data["fecha_inicial"]), 1, 1),
                    fecha_final=date(int(form.cleaned_data["fecha_final"]), 1, 1),
                    comentario=form.cleaned_data["comentario"],
                    estado="pendiente"
                )
                
                # Devolver éxito PERO sin recargar la página
                return JsonResponse({
                    'success': True,
                    'message': 'Solicitud de constancia enviada correctamente.'
                })
                
            except Exception as e:
                print(f"Error al guardar: {e}")
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': ['Error al procesar la solicitud']}
                }, status=500)
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return JsonResponse({'error': 'Método no permitido'}, status=400)

@login_required
def user_dashboard_solicitud(request):
    user = request.user

    initial_data = {
        "nombre_completo": f"{user.nombres} {user.apellidos}",
        "numero_documento": user.numero_documento,
        "tipo_documento": user.tipo_documento,
        "email": user.email,
    }

    if request.method == "POST":
        form = ConstanciaForm(request.POST, initial=initial_data)
        if form.is_valid():
            Constancia.objects.create(
                usuario=user,
                fecha_inicial=date(int(form.cleaned_data["fecha_inicial"]), 1, 1),
                fecha_final=date(int(form.cleaned_data["fecha_final"]), 1, 1),
                
            )
            messages.success(request, "Solicitud de constancia enviada correctamente.")
            return redirect("user_dashboard")
    else:
        form = ConstanciaForm(initial=initial_data)

    solicitudes = Constancia.objects.filter(usuario=user).order_by("-creado_en")

    return render(
        request,
        "users/user/dashboard.html",
        {"form": form, "solicitudes": solicitudes}
    )

# Gestión de roles (solo para admins)
# views.py
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Rol

# Gestión de roles (solo para admins)
@login_required
def manage_roles(request):
    # Verificamos que solo los usuarios con rol "Administrador" puedan acceder
    if not request.user.role or request.user.role.nombre.lower() != "administrador":
        return redirect("admin_dashboard")  

    users = CustomUser.objects.all()
    roles = Rol.objects.all()  # Para listarlos en el template

    # Si se recibe una solicitud POST para eliminar o agregar un rol
    if request.method == "POST":
        action = request.POST.get("action")
        
        # Si la acción es para eliminar un rol
        if action == "delete_role":
            role_id = request.POST.get("role_id")
            try:
                role = Rol.objects.get(id=role_id)
                role.delete()  # Eliminamos el rol de la base de datos
                messages.success(request, f"Rol '{role.nombre}' eliminado exitosamente.")
            except Rol.DoesNotExist:
                messages.error(request, "El rol que intentas eliminar no existe.")
        
        # Si la acción es para agregar un nuevo rol
        elif action == "add_role":
            nombre_rol = request.POST.get("nombre_rol")
            descripcion_rol = request.POST.get("descripcion")
            
            if nombre_rol:
                # Creamos el nuevo rol
                new_role = Rol.objects.create(
                    nombre=nombre_rol,
                    descripcion=descripcion_rol
                )
                messages.success(request, f"Rol '{new_role.nombre}' creado exitosamente.")
            else:
                messages.error(request, "El nombre del rol es obligatorio.")
        
        # Si se está asignando un rol a un usuario
        elif "user_id" in request.POST and "role_id" in request.POST:
            user_id = request.POST.get("user_id")
            new_role_id = request.POST.get("role_id")

            try:
                user = CustomUser.objects.get(id=user_id)
                new_role = get_object_or_404(Rol, id=new_role_id)  # obtenemos el objeto Rol
                user.role = new_role  # Asignamos el objeto Rol al usuario
                user.save()
                messages.success(request, f"Rol de {user.nombres} {user.apellidos} actualizado a '{new_role.nombre}'.")
            except CustomUser.DoesNotExist:
                messages.error(request, "Usuario no encontrado.")
        
        return redirect("manage_roles")  # Redirigimos de nuevo a la página de gestión de roles

    return render(
        request,
        "users/roles/manage_roles.html",  # Ruta al template
        {"users": users, "roles": roles},
    )
