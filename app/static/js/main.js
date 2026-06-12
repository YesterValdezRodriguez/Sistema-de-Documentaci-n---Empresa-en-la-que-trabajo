// QMS FARACH - JavaScript principal
document.addEventListener('DOMContentLoaded', function () {
    // Auto-ocultar mensajes flash después de 6 segundos
    document.querySelectorAll('.alert-flash').forEach(function (alerta) {
        setTimeout(function () {
            alerta.classList.remove('show');
            setTimeout(function () { alerta.remove(); }, 300);
        }, 6000);
    });

    // Activar tooltips de Bootstrap
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // Confirmación genérica para formularios destructivos
    document.querySelectorAll('form[data-confirmar]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!window.confirm(form.dataset.confirmar)) {
                e.preventDefault();
            }
        });
    });
});
