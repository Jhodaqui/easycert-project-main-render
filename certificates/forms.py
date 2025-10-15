from django import forms

class StaffFillForm(forms.Form):
    numero_contrato = forms.CharField(label="Número de contrato", required=False)
    fecha_generacion = forms.DateField(label="Fecha de generación", required=False, widget=forms.DateInput(attrs={"type":"date"}))
    valor_total = forms.CharField(label="Valor total", required=False)
    forma_pago = forms.CharField(label="Forma de pago", required=False)
    fecha_expedicion_texto = forms.CharField(
        label="Fecha de expedición (ej. 'diez (10) días de febrero de 2025')",
        required=False
    )

class ManualFieldsForm(forms.Form):
    numero_contrato = forms.CharField(label="Número de contrato", required=True)
    fecha_contrato = forms.DateField(
        label="Fecha del contrato",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"})
    )
    fecha_expedicion = forms.CharField(
        label="Fecha de expedición (ej: diez (10) días de febrero de 2025)",
        required=True
    )


class ConstanciaGenerateForm(forms.Form):
    confirmar = forms.BooleanField(label="Confirmo que los datos son correctos", required=True)