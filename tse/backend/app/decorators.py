from functools import wraps

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

from app.models import Usuario


def rol_requerido(*roles_permitidos):
    """
    Decorador para rutas que requieren JWT válido y que el usuario
    tenga uno de los roles indicados (Usuario.ROL_ADMIN, ROL_OPERADOR, ROL_AUDITOR).

    Uso:
        @rol_requerido(Usuario.ROL_ADMIN)
        @rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_OPERADOR)
    """

    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            rol_id = claims.get("rol_id")

            if rol_id not in roles_permitidos:
                return jsonify({"error": "No tiene permisos para esta acción"}), 403

            return func(*args, **kwargs)

        return wrapper

    return decorador


def jwt_requerido(func):
    """Solo exige JWT válido, sin restricción de rol (cualquier usuario TSE autenticado)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        return func(*args, **kwargs)

    return wrapper


def usuario_actual() -> Usuario | None:
    identidad = get_jwt_identity()
    if identidad is None:
        return None
    return Usuario.query.get(int(identidad))
