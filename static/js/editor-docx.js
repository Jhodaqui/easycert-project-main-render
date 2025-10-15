// static/js/editor-docx.js
document.addEventListener("alpine:init", () => {

  // --- Store principal: listado de DOCX ---
  Alpine.store("docxEditor", {
    open: false,
    userId: null,
    files: [],

    async openForUser(userId) {
      this.userId = userId;
      this.open = true;
      this.files = [];

      try {
        const res = await fetch(`/documents/listar-docx-guardados/${userId}/`, { credentials: "include" });
        const data = await res.json();
        if (data.ok) {
          this.files = data.files || [];
        } else {
          Swal.fire("⚠️", data.error || "No se encontraron archivos", "warning");
        }
      } catch (err) {
        console.error(err);
        Swal.fire("❌ Error", "No se pudieron cargar los archivos", "error");
      }
    },

    openPreview(filename) {
      Alpine.store("previewDocx").openForFile(this.userId, filename);
    },

    async refreshList() {
      // 🧩 Validación robusta del userId
      if (!this.userId || this.userId === "null" || isNaN(this.userId)) {
        console.warn("⏭️ No se refresca lista: userId inválido ->", this.userId);
        return;
      }

      try {
        const res = await fetch(`/documents/listar-docx-guardados/${this.userId}/`, { credentials: "include" });
        const data = await res.json();
        if (data.ok) this.files = data.files || [];
      } catch (err) {
        console.error("Error actualizando lista:", err);
      }
    },

    close() {
      this.open = false;
      this.userId = null;
      this.files = [];
    },
  });

  // --- Store de vista previa DOCX ---
  Alpine.store("previewDocx", {
    open: false,
    userId: null,
    fileName: null,
    awaitingUpload: false,
    showEditedAlert: false,
    dragging: false,

    async openForFile(userId, filename) {
      this.userId = userId;
      this.fileName = filename;
      this.open = true;
      this.awaitingUpload = false;
      this.showEditedAlert = false;

      const container = document.getElementById("docx-preview-container");
      container.innerHTML = "<p class='text-gray-500'>Cargando vista previa...</p>";

      try {
        const url = `/documents/contratos/preview/${userId}/${encodeURIComponent(filename)}/`;
        const res = await fetch(url);
        if (!res.ok) throw new Error("No se pudo cargar el archivo");

        const blob = await res.blob();
        container.innerHTML = "";
        await window.docx.renderAsync(blob, container, null, {
          className: "docx-preview",
          inWrapper: true,
        });
      } catch (err) {
        console.error(err);
        container.innerHTML = `<div class="text-red-600">Error cargando vista previa</div>`;
      }
    },

    async startDownload() {
      Swal.fire({
        title: "📥 Descargando...",
        text: "Por favor edita el documento y súbelo nuevamente",
        showConfirmButton: false,
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading(),
      });

      const a = document.createElement("a");
      a.href = `/documents/contratos/download/${this.userId}/${this.fileName}`;
      a.download = this.fileName;
      a.click();

      Swal.close();
      this.awaitingUpload = true;

      const container = document.getElementById("docx-preview-container");
      container.innerHTML = `
        <div class='p-6 text-center text-gray-600 border-2 border-dashed border-gray-300 rounded-lg'>
          <p class="mb-3">✳️ Arrastra o selecciona el documento editado para continuar.</p>
          <label class="cursor-pointer px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 inline-block">
            Seleccionar archivo
            <input type="file" class="hidden" @change="$store.previewDocx.uploadEdited($event)">
          </label>
        </div>
      `;
    },

    // ✅ Función corregida para soportar arrastre y selección
    async uploadEdited(event) {
      const file =
        event?.target?.files?.[0] ||
        event?.dataTransfer?.files?.[0] ||
        null;

      if (!file) {
        console.warn("⚠️ No se detectó archivo al subir (event.target o dataTransfer vacío)");
        return;
      }

      Swal.fire({
        title: "Subiendo...",
        text: "Procesando documento editado",
        showConfirmButton: false,
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading(),
      });

      const formData = new FormData();
      formData.append("archivo", file);

      try {
        const res = await fetch(`/documents/contratos/upload/${this.userId}/`, {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: { "X-CSRFToken": csrfToken },
        });
        const data = await res.json();

        if (data.ok) {
          Swal.fire({
            title: "✅ Documento actualizado",
            text: "Se mostrará la vista previa del archivo actualizado.",
            icon: "success",
            timer: 1500,
            showConfirmButton: false,
          });

          setTimeout(async () => {
            await this.openForFile(this.userId, this.fileName);
            this.awaitingUpload = false;
            this.showEditedAlert = true;
            if (this.userId) Alpine.store("docxEditor").refreshList();
          }, 1500);
        } else {
          Swal.fire("❌", data.error || "Error al subir archivo", "error");
        }
      } catch (err) {
        console.error(err);
        Swal.fire("❌ Error", "Error subiendo archivo", "error");
      }
    },

    async handleDrop(event) {
      this.dragging = false;
      await this.uploadEdited(event);
    },

    resetUpload() {
      this.showEditedAlert = false;
      this.awaitingUpload = true;
      const container = document.getElementById("docx-preview-container");
      container.innerHTML = `
        <div class='p-6 text-center text-gray-600 border-2 border-dashed border-gray-300 rounded-lg'>
          <p class="mb-3">✳️ Arrastra o selecciona el documento editado para continuar.</p>
          <label class="cursor-pointer px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 inline-block">
            Seleccionar archivo
            <input type="file" class="hidden" @change="$store.previewDocx.uploadEdited($event)">
          </label>
        </div>
      `;
    },

    // ✅ Corrige bug del userId null al refrescar después de guardar
    async confirmSave() {
      Swal.fire("✅ Documento actualizado", "Los cambios se han guardado correctamente", "success");

      const savedUserId = this.userId; // guardamos antes de cerrar

      setTimeout(() => {
        this.close();
        if (savedUserId) {
          Alpine.store("docxEditor").openForUser(savedUserId);
        }
      }, 1200);
    },

    close() {
      if (this.awaitingUpload && !this.showEditedAlert) return;
      this.open = false;
      this.userId = null;
      this.fileName = null;
      this.awaitingUpload = false;
      this.showEditedAlert = false;
      this.dragging = false;
      const container = document.getElementById("docx-preview-container");
      if (container) container.innerHTML = "";
    },
  });
});
