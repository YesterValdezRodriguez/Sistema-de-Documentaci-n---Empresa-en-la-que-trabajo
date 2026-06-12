"""Decoradores de autorización por rol."""
from functools import wraps
from flask import abort
from flask_login import current_user


def rol_requerido(*roles):
    """Restringe el acceso a usuarios con alguno de los roles indicados.

    El rol `admin` siempre tiene acceso.
    """
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.rol != 'admin' and current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return envoltura
    return decorador
