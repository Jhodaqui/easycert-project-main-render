// static/js/user_dashboard.js
document.addEventListener("DOMContentLoaded", () => {
  const abrirBtn = document.getElementById("abrirFormularioBtn");
  const modalEl = document.getElementById("formularioModal");
  const modalBody = document.getElementById("modalFormularioContenido");

  let formDirty = false;
  let formOpened = false;
  let formSubmitted = false;
  let forceReload = false;

  // advertencia al salir
  window.addEventListener("beforeunload", (e) => {
    if (formOpened && formDirty && !formSubmitted && !forceReload) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  // abrir modal y cargar form
  abrirBtn.addEventListener("click", () => {
    // Mostrar modal (Tailwind: quitar hidden)
    modalEl.classList.remove("hidden");
    // limpiar contenido previo
    modalBody.innerHTML = '<p class="text-center text-gray-500 py-6">Cargando...</p>';

    fetch("/users/formulario-constancia/", {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Error cargando formulario");
        return res.json();
      })
      .then((data) => {
        modalBody.innerHTML = data.form_html;

        const form = document.getElementById("constanciaForm");
        if (form) {
          formOpened = true;
          formDirty = false;
          formSubmitted = false;

          // listeners para detectar cambios
          form.addEventListener("input", () => (formDirty = true));
          form.addEventListener("change", () => (formDirty = true));
          form.addEventListener("submit", handleSubmit);
        }
      })
      .catch(() => {
        modalBody.innerHTML =
          '<div class="text-red-600 p-4">Error al cargar el formulario. Intente nuevamente.</div>';
      });
  });

  // cerrar modal si se clic en fondo o en botón con data-close
  modalEl.addEventListener("click", (e) => {
    // si clic fuera del contenido (el overlay) o en elemento con data-close="modal"
    const target = e.target;
    if (target === modalEl || target.dataset.close === "modal") {
      modalEl.classList.add("hidden");
    }
  });

  // Envío del formulario con validaciones cliente
  function handleSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector("button[type=submit]");

    // limpiar errores previos
    clearClientErrors(form);

    // validación cliente: fechas
    const startSel = form.querySelector('[name="fecha_inicial"]');
    const endSel = form.querySelector('[name="fecha_final"]');

    // extraer valores
    const startVal = startSel ? startSel.value.trim() : "";
    const endVal = endSel ? endSel.value.trim() : "";

    let hasClientError = false;

    if (!startVal) {
      showClientError(startSel, "Selecciona el año de inicio.");
      hasClientError = true;
    }
    if (!endVal) {
      showClientError(endSel, "Selecciona el año de fin.");
      hasClientError = true;
    }

    if (!hasClientError) {
      const startYear = parseInt(startVal, 10);
      const endYear = parseInt(endVal, 10);

      if (isNaN(startYear) || isNaN(endYear)) {
        showClientError(startSel || form, "Año inválido.");
        hasClientError = true;
      } else if (endYear < startYear) {
        showClientError(endSel, "El año final no puede ser menor que el inicial.");
        hasClientError = true;
      }
    }

    if (hasClientError) {
      // evitar envío; reenfocar al primer error
      const firstErr = form.querySelector(".client-error, .client-error-inline");
      if (firstErr && firstErr.previousElementSibling) firstErr.previousElementSibling.focus();
      return;
    }

    // preparar envío
    const formData = new FormData(form);

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Enviando...";
    }

    fetch("/users/procesar-constancia/", {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getCookie("csrftoken"),
      },
    })
      .then((res) => {
        // puede ser 400 con json de errores
        if (!res.ok) return res.json().then((d) => { throw d; });
        return res.json();
      })
      .then((data) => {
        if (data.success) {
          formSubmitted = true;
          formDirty = false;

          modalBody.innerHTML = `
            <div class="text-center text-green-600 p-6">
              <h4 class="font-bold">¡Solicitud enviada!</h4>
              <p class="mt-2">${data.message}</p>
              <p class="mt-2 text-gray-500">La página se recargará...</p>
            </div>
          `;

          setTimeout(() => {
            forceReload = true;
            window.location.reload();
          }, 1400);
        } else {
          // errores de validación del servidor
          if (data.errors) {
            renderErrors(form, data.errors);
          } else {
            showTopError(form, "Error al procesar la solicitud.");
          }
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Solicitar";
          }
        }
      })
      .catch((err) => {
        // err puede ser objeto con errores o una excepción
        if (err && typeof err === "object" && err.errors) {
          renderErrors(document.getElementById("constanciaForm"), err.errors);
        } else {
          showTopError(document.getElementById("constanciaForm"), "Error en la conexión. Intenta de nuevo.");
        }
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Solicitar";
        }
      });
  }

  // ------- Helpers de errores cliente/servidor -------
  function clearClientErrors(form) {
    if (!form) return;
    // elimina mensajes previos con clase client-error
    form.querySelectorAll(".client-error, .client-error-inline").forEach(el => el.remove());
    // limpiar contenedor top
    const top = form.querySelector("#formErrorsTop");
    if (top) top.innerHTML = "";
  }

  function showClientError(inputEl, message) {
    if (!inputEl) return;
    const err = document.createElement("div");
    err.className = "client-error text-red-500 text-sm mt-1";
    err.textContent = message;
    // intentar colocar después del input/selector; si existe un contenedor .client-error-container lo usamos
    const container = inputEl.closest("div")?.querySelector(".client-error-container");
    if (container) container.appendChild(err);
    else inputEl.insertAdjacentElement("afterend", err);
    // marcar aria
    try { inputEl.setAttribute("aria-invalid", "true"); } catch(e){}
  }

  function showTopError(form, message) {
    if (!form) return;
    const top = form.querySelector("#formErrorsTop");
    if (top) {
      top.textContent = message;
    } else {
      const e = document.createElement("div");
      e.className = "client-error text-red-600 text-sm mb-2";
      e.textContent = message;
      form.prepend(e);
    }
  }

  // renderización de errores provenientes del servidor (igual que antes)
  function renderErrors(form, errors) {
    if (!form || !errors) return;
    // limpiar errores previos
    clearClientErrors(form);
    for (const [field, msgs] of Object.entries(errors)) {
      const input = form.querySelector(`[name="${field}"]`);
      if (input) {
        const errorSpan = document.createElement("div");
        errorSpan.className = "client-error-inline text-red-500 text-sm mt-1";
        errorSpan.textContent = Array.isArray(msgs) ? msgs.join(", ") : msgs;
        input.insertAdjacentElement("afterend", errorSpan);
      } else {
        // error general
        showTopError(form, Array.isArray(msgs) ? msgs.join(", ") : msgs);
      }
    }
  }

  // cookie helper
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let c of cookies) {
        c = c.trim();
        if (c.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(c.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
});
