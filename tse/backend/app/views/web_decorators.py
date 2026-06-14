from functools import wraps

from flask import redirect, url_for, flash, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity

from app.models import Usuario


def _cargar_usuario_actual():
    """
    Verifica el JWT (cookie o header) y deja en g.usuario un dict
    con los datos básicos para el template (nombre, rol, recinto).
    Lanza la excepción correspondiente si no hay sesión válida.
    """
    verify_jwt_in_request()
    claims = get_jwt()
    g.usuario = {
        "id": int(get_jwt_identity()),
        "rol_id": claims.get("rol_id"),
        "rol_nombre": claims.get("rol_nombre"),
        "nombre_completo": claims.get("nombre_completo"),
        "recinto_id": claims.get("recinto_id"),
    }


def login_requerido(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            _cargar_usuario_actual()
        except Exception:
            flash("Tu sesión expiró o no has iniciado sesión. Vuelve a ingresar.", "error")
            return redirect(url_for("auth_web.login"))
        return func(*args, **kwargs)

    return wrapper


def rol_web_requerido(*roles_permitidos):
    """Igual que login_requerido, pero además exige uno de los roles indicados."""

    def decorador(func):
        @wraps(func)
        @login_requerido
        def wrapper(*args, **kwargs):
            if g.usuario["rol_id"] not in roles_permitidos:
                flash("No tienes permisos para acceder a esa sección.", "error")
                return redirect(url_for("panel.inicio"))
            return func(*args, **kwargs)

        return wrapper

    return decorador


def usuario_actual_completo() -> Usuario | None:
    """Devuelve el objeto Usuario completo desde la BD (para datos no incluidos en el JWT)."""
    return Usuario.query.get(g.usuario["id"])
