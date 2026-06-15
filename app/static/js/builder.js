// QMS FARACH — Armador de expedientes (drag & drop + vista previa)
(function () {
  'use strict';

  function tokenCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  // ---------- Vista previa (carga diferida del iframe) ----------
  var modalPreview = document.getElementById('modalPreview');
  if (modalPreview) {
    var frame = document.getElementById('preview-frame');
    modalPreview.addEventListener('shown.bs.modal', function () {
      var src = frame.getAttribute('data-src');
      frame.src = src + (src.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
    });
    modalPreview.addEventListener('hidden.bs.modal', function () {
      frame.src = 'about:blank';
    });
  }

  // ---------- Reordenar por arrastre ----------
  var lista = document.getElementById('lista-items');
  if (!lista) { return; }
  var urlReordenar = lista.getAttribute('data-url-reordenar');

  function elementosArrastrables() {
    return Array.prototype.slice.call(lista.querySelectorAll('.item-expediente'));
  }

  function despuesDe(contenedor, y) {
    var items = elementosArrastrables().filter(function (el) {
      return !el.classList.contains('dragging');
    });
    var resultado = { offset: Number.NEGATIVE_INFINITY, element: null };
    items.forEach(function (child) {
      var box = child.getBoundingClientRect();
      var offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > resultado.offset) {
        resultado = { offset: offset, element: child };
      }
    });
    return resultado.element;
  }

  function renumerar() {
    elementosArrastrables().forEach(function (row, i) {
      var n = row.querySelector('.orden-num');
      if (n) { n.textContent = i + 1; }
      // primer botón subir / último botón bajar deshabilitados
      var subir = row.querySelector('button[title="Subir"]');
      var bajar = row.querySelector('button[title="Bajar"]');
      if (subir) { subir.disabled = (i === 0); }
      if (bajar) { bajar.disabled = (i === elementosArrastrables().length - 1); }
    });
  }

  function guardarOrden() {
    var ids = elementosArrastrables().map(function (r) { return r.getAttribute('data-item-id'); });
    fetch(urlReordenar, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': tokenCSRF() },
      body: JSON.stringify({ orden: ids })
    }).then(function () { renumerar(); }).catch(function () {
      // si falla, recargar para no quedar inconsistente con el servidor
      window.location.reload();
    });
  }

  elementosArrastrables().forEach(function (row) {
    if (row.getAttribute('draggable') !== 'true') { return; }
    row.addEventListener('dragstart', function () {
      row.classList.add('dragging');
      row.style.opacity = '0.5';
    });
    row.addEventListener('dragend', function () {
      row.classList.remove('dragging');
      row.style.opacity = '';
      guardarOrden();
    });
  });

  lista.addEventListener('dragover', function (e) {
    e.preventDefault();
    var dragging = lista.querySelector('.dragging');
    if (!dragging) { return; }
    var ref = despuesDe(lista, e.clientY);
    if (ref == null) {
      lista.appendChild(dragging);
    } else {
      lista.insertBefore(dragging, ref);
    }
  });
})();
