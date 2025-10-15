// static/js/dashboard.js
document.addEventListener("alpine:init", () => {
  Alpine.data("dashboard", () => ({
    // Estados
    openListModal: false,
    openFormModal: false,
    currentUserId: null,
    search: "",
    prefilled: false,
    formModalHasErrors: false,
    fileUploaded: false,
    fileName: "",

    contratos: [],

    formData: {
      contrato_id: null,
      usuario_id: null,
      numero_contrato: "",
      objeto: "",
      objetivos_especificos: "",
      valor_pago: "",
      fecha_inicio: "",
      fecha_fin: "",
      fecha_generacion: "",
    },

    editable: {
      objeto: false,
      objetivos: false,
    },

    // Inicialización Alpine
    init() {
      // nada extra, Alpine maneja x-show/x-cloak
    },

    // Helpers UI
    resetForm() {
      this.formData = {
        contrato_id: null,
        usuario_id: this.currentUserId,
        numero_contrato: "",
        objeto: "",
        objetivos_especificos: "",
        valor_pago: "",
        fecha_inicio: "",
        fecha_fin: "",
        fecha_generacion: "",
      };
      this.prefilled = false;
      this.fileUploaded = false;
      this.fileName = "";
      this.formModalHasErrors = false;

      // limpiar errores
      const errors = document.getElementById("formModalErrors");
      if (errors) errors.innerHTML = "";

      // reset editable flags
      this.editable.objeto = false;
      this.editable.objetivos = false;
    }, // resetForm

    showFormErrors(errs) {
      this.formModalHasErrors = true;
      const errors = document.getElementById("formModalErrors");
      if (!errors) return;
      errors.innerHTML = "";
      for (const k in errs) {
        const msgs = errs[k];
        if (Array.isArray(msgs)) {
          msgs.forEach((m) => (errors.innerHTML += `<div>${k}: ${m}</div>`));
        } else {
          errors.innerHTML += `<div>${k}: ${msgs}</div>`;
        }
      }
    }, // showFormErrors

    filterTable(rowText) {
      if (!this.search) return true;
      return rowText.toLowerCase().includes(this.search.toLowerCase());
    }, // filterTable

    // Abrir listado de contratos
    async openListForUser(userId) {
      this.currentUserId = userId;
      this.formData.usuario_id = userId;
      this.openListModal = true;
      await this.refrescarContratos();
    }, // openListForUser

    // Abrir formulario nuevo
    openFormForUser(userId) {
      this.currentUserId = userId;
      this.formData.usuario_id = userId;
      this.resetForm();
      this.openFormModal = true;
    }, // openFormForUser

    async refrescarContratos() {
      if (!this.currentUserId) return;
      const listModalBody = document.getElementById("contratosModalBody");
      try {
        listModalBody.innerHTML = `<p class="text-gray-500">Cargando contratos...</p>`;
        const res = await fetch(`${urls.verContratosBase}${this.currentUserId}/`);
        const data = await res.json();
        listModalBody.innerHTML = `
          <div id="contratosCargadosWrapper" class="mt-2">
            <div class="overflow-x-auto">${data.html}</div>
          </div>
        `;
        this.bindAccionesContratos();
      } catch (err) {
        console.error("Error refrescando contratos:", err);
        listModalBody.innerHTML = `<div class="text-red-600">Error cargando contratos.</div>`;
      }
    }, // refrescarContratos

    bindAccionesContratos() {
      // Select/deselect all
      const selectAll = document.getElementById("selectAllContratos");
      const checkboxes = document.querySelectorAll("#contratosCargadosWrapper .contrato-checkbox");

      if (selectAll) {
        selectAll.addEventListener("change", () => {
          checkboxes.forEach((cb) => (cb.checked = selectAll.checked));
        });
      }

      // sincronizar header con hijos
      checkboxes.forEach((cb) => {
        cb.addEventListener("change", () => {
          if (!selectAll) return;
          const allChecked = [...checkboxes].every((c) => c.checked);
          const someChecked = [...checkboxes].some((c) => c.checked);
          selectAll.checked = allChecked;
          selectAll.indeterminate = !allChecked && someChecked;
        });
      });

      // PDF individual
      document.querySelectorAll(".generar-pdf").forEach((btn) => {
        btn.addEventListener("click", () => {
          const contratoId = btn.dataset.id;
          window.open(`/documents/contrato/pdf/${this.currentUserId}/${contratoId}/`, "_blank");
        });
      });

      // Ver/editar detalle
      document.querySelectorAll(".ver-detalle").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const contratoId = btn.dataset.id;
          try {
            const res = await fetch(`/documents/contrato/${contratoId}/`);
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || "Error en servidor");

            const c = data.contrato;
            this.resetForm();
            this.formData = { ...this.formData, ...c, contrato_id: contratoId };

            // actualizar inputs DOM
            Object.keys(this.formData).forEach((k) => {
              const el = document.getElementById(`id_${k}`);
              if (el) el.value = this.formData[k] || "";
            });

            if (c.objeto || c.objetivos_especificos) {
              this.prefilled = true;
              this.fileUploaded = true;
              this.fileName = c.numero_contrato ? `${c.numero_contrato}.pdf` : "";
            }

            this.openFormModal = true;
            Swal.fire({
              title: "📑 Contrato cargado",
              text: "Listo para edición",
              icon: "info",
              timer: 1200,
              showConfirmButton: false,
            });
          } catch (err) {
            console.error(err);
            Swal.fire("❌ Error", "Error cargando contrato", "error");
          }
        });
      });
    }, // bindAccionesContratos

    // Generar paquete (individual o bloque)
    async generarPaquete(tipo) {
    if (!this.currentUserId) return;

    const selected = [...document.querySelectorAll("#contratosCargadosWrapper .contrato-checkbox:checked")]
      .map(cb => cb.value)
      .join(",");

    if (!selected) {
      Swal.fire("⚠️", "Debes seleccionar al menos un contrato.", "warning");
      return;
    }

    const url = tipo === "individual"
      ? `/documents/generate-individual/${this.currentUserId}/`
      : `/documents/contratos/bloques/${this.currentUserId}/`;

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: new URLSearchParams({ selected_ids: selected }),
        credentials: "include"
      });

      const contentType = res.headers.get("content-type") || "";
      if (!res.ok) {
        if (contentType.includes("application/json")) {
          const data = await res.json();
          throw new Error(data.error || "Error generando documentos");
        }
        throw new Error("Error inesperado al generar documentos");
      }

      if (tipo === "individual") {
        // 🔹 Flujo INDIVIDUAL → JSON
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "Error en servidor");

        Swal.fire("✅", "Certificados individuales generados con éxito", "success");

        // refrescar lista de DOCX en el modal de gestión
        Alpine.store("docxEditor").openForUser(this.currentUserId);
      } else {
        // 🔹 Flujo BLOQUE → ZIP
        const blob = await res.blob();
        const link = document.createElement("a");
        link.href = window.URL.createObjectURL(blob);
        link.download = "certificados_bloque.zip";
        document.body.appendChild(link);
        link.click();
        link.remove();

        Swal.fire("✅", "Documento en bloque generado con éxito", "success");
      }
    } catch (err) {
      console.error(err);
      Swal.fire("❌ Error", err.message || "Error al generar documentos", "error");
    }
  }, // generarPaquete

    // Maneja el cambio del file input
    async handleFileChange(e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      this.fileName = file.name;

      const formData = new FormData();
      formData.append("archivo", file);

      try {
        const res = await fetch(urls.prefillContrato, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: formData,
        });
        const data = await res.json();

        if (!res.ok || !data.ok) {
          Swal.fire("⚠️", data.error || "No se pudo procesar el PDF", "warning");
          e.target.value = "";
          this.fileUploaded = false;
          this.fileName = "";
          return;
        }

        const m = data.metadata || {};
        this.formData.valor_pago = m.valor_pago || this.formData.valor_pago;
        this.formData.fecha_fin = m.plazo_fecha || this.formData.fecha_fin;
        this.formData.fecha_inicio = m.fecha_inicio || this.formData.fecha_inicio;
        this.formData.fecha_generacion = m.fecha_generacion || this.formData.fecha_generacion;
        if (m.objeto) this.formData.objeto = m.objeto;
        if (m.objetivos_especificos) this.formData.objetivos_especificos = m.objetivos_especificos;

        this.prefilled = true;
        this.fileUploaded = true;

        Object.keys(this.formData).forEach((k) => {
          const el = document.getElementById(`id_${k}`);
          if (el) el.value = this.formData[k] || "";
        });

        Swal.fire({
          title: "✳️ Prellenado",
          text: "Se extrajeron datos del PDF",
          icon: "success",
          timer: 1300,
          showConfirmButton: false,
        });
      } catch (err) {
        console.error(err);
        Swal.fire("⚠️ Error", "Error al enviar PDF para prellenar.", "error");
        e.target.value = "";
        this.fileUploaded = false;
        this.fileName = "";
      }
    }, // handleFileChange

    // Guardar contrato
    async guardarContrato() {
      const fd = new FormData();
      if (this.formData.contrato_id) fd.append("contrato_id", this.formData.contrato_id);
      if (this.formData.usuario_id) fd.append("usuario_id", this.formData.usuario_id);
      if (this.formData.numero_contrato) fd.append("numero_contrato", this.formData.numero_contrato);
      if (this.formData.valor_pago) fd.append("valor_pago", this.formData.valor_pago);
      if (this.formData.fecha_inicio) fd.append("fecha_inicio", this.formData.fecha_inicio);
      if (this.formData.fecha_fin) fd.append("fecha_fin", this.formData.fecha_fin);
      if (this.formData.fecha_generacion) fd.append("fecha_generacion", this.formData.fecha_generacion);
      if (this.formData.objeto) fd.append("objeto", this.formData.objeto);
      if (this.formData.objetivos_especificos) fd.append("objetivos_especificos", this.formData.objetivos_especificos);

      try {
        const res = await fetch(urls.contratoCreate, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: fd,
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          this.showFormErrors(data.errors || data);
          return;
        }

        this.openFormModal = false;
        if (this.openListModal) await this.refrescarContratos();
        Swal.fire("✅ Guardado", "Contrato guardado correctamente", "success");
      } catch (err) {
        console.error(err);
        Swal.fire("❌ Error", "Error guardando contrato", "error");
      }
    }, // guardarContrato
  })); // Alpine.data
}); // document.addEventListener
