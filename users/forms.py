from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import CustomUser, TIPOS_DOCUMENTO, Constancia, dptos, municipios
from datetime import datetime

# Dominios permitidos
ALLOWED_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "sena.edu.co"
}

AÑO_ACTUAL = datetime.now().year
AÑOS = [(str(a), str(a)) for a in range(1990, AÑO_ACTUAL + 1)]


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput,
        required=True,
        min_length=8,
        help_text="La contraseña debe tener al menos 8 caracteres."
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput,
        required=True
    )

    # Campos personalizados
    nombres = forms.CharField(
        max_length=100,
        validators=[RegexValidator(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', "Solo letras y espacios")],
        label="Nombres"
    )
    apellidos = forms.CharField(
        max_length=100,
        validators=[RegexValidator(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', "Solo letras y espacios")],
        label="Apellidos"
    )
    tipo_documento = forms.ChoiceField(
        choices=TIPOS_DOCUMENTO,
        label="Tipo de documento"
    )
    numero_documento = forms.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\d{1,15}$', "Solo números, máximo 15 dígitos")],
        label="Número de documento"
    )
    email = forms.EmailField(label="Correo electrónico")

    # Nuevos campos relacionados
    departamento = forms.ModelChoiceField(
        queryset=dptos.objects.all(),
        label="Departamento",
        required=True
    )
    centro = forms.ModelChoiceField(
        queryset=municipios.objects.none(),
        label="Centro de formación",
        required=True
    )

    class Meta:
        model = CustomUser
        fields = [
            "nombres",
            "apellidos",
            "tipo_documento",
            "numero_documento",
            "departamento",
            "centro",
            "email",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🔹 Agregar estilos Bootstrap
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({"class": "form-select"})
            else:
                field.widget.attrs.update({"class": "form-control"})

        # Lógica de selects dependientes
        if "departamento" in self.data:
            try:
                depto_id = int(self.data.get("departamento"))
                self.fields["centro"].queryset = municipios.objects.filter(idDepto_id=depto_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields["centro"].queryset = municipios.objects.filter(idDepto=self.instance.departamento)

    # Validación de correo
    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        domain = email.split("@")[-1]

        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise ValidationError(
                "El correo debe ser de un dominio válido: Gmail, Outlook, Hotmail, sena.edu.co, etc."
            )
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("Este correo ya está registrado.")
        return email

    # Validación de contraseñas
    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            raise ValidationError("Las contraseñas no coinciden.")
        return cleaned

    # Guardar usuario
    def save(self, commit=True):
        user = super().save(commit=False)
        user.nombres = self.cleaned_data["nombres"]
        user.apellidos = self.cleaned_data["apellidos"]
        user.tipo_documento = self.cleaned_data["tipo_documento"]
        user.numero_documento = self.cleaned_data["numero_documento"]
        user.email = self.cleaned_data["email"].lower()
        user.departamento = self.cleaned_data["departamento"]
        user.centro = self.cleaned_data["centro"]
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
        return user


class BulkUploadForm(forms.Form):
    file = forms.FileField(
        label="Archivo de usuarios (CSV o Excel)",
        help_text="Sube un archivo con columnas: nombres, apellidos, tipo_documento, numero_documento, email, password"
    )


class MunicipiosUploadForm(forms.Form):
    file = forms.FileField(label="Selecciona el archivo CSV")


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ingresa tu correo electrónico",
                "autocomplete": "email",
            }
        )
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if not CustomUser.objects.filter(email=email, is_active=True).exists():
            raise ValidationError("No existe un usuario activo con este correo.")
        return email


class ConstanciaForm(forms.Form):
    nombre_completo = forms.CharField(label="Nombre Completo", disabled=True)
    numero_documento = forms.CharField(label="Número Documento", disabled=True)
    tipo_documento = forms.CharField(label="Tipo Documento", disabled=True)
    email = forms.EmailField(label="Correo electrónico", disabled=True)

    # fechas por año
    fecha_inicial = forms.ChoiceField(
        label="Año inicial de la constancia",
        choices=AÑOS
    )
    fecha_final = forms.ChoiceField(
        label="Año final de la constancia",
        choices=AÑOS
    )

    comentario = forms.CharField(
        label="Comentario",
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Escribe tu comentario aquí...",
            "rows": 4,
            "cols": 40
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        año_inicial = int(cleaned_data.get("fecha_inicial", 0))
        año_final = int(cleaned_data.get("fecha_final", 0))

        if año_inicial > año_final:
            self.add_error("fecha_inicial", "El año inicial no puede ser mayor que el año final.")
            self.add_error("fecha_final", "El año final no puede ser menor que el año inicial.")

        return cleaned_data