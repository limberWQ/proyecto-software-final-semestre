from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt

from app.models import Usuario
from app.services import auth_service
from app.decorators import rol_requerido, usuario_actual

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email y password son requeridos"}), 400

    try:
        usuario = auth_service.autenticar(email, password, ip=request.remote_addr)
    except auth_service.AuthError as e:
        return jsonify({"error": str(e)}), 401

    token = create_access_token(
        identity=str(usuario.id),
        additional_claims={
            "rol_id": usuario.rol_id,
            "rol_nombre": usuario.rol.nombre,
            "nombre_completo": usuario.nombre_completo,
            "recinto_id": usuario.recinto_id,
        },
    )

    return jsonify(
        {
            "access_token": token,
            "usuario": {
                "id": usuario.id,
                "ci": usuario.ci,
                "nombre_completo": usuario.nombre_completo,
                "email": usuario.email,
                "rol_id": usuario.rol_id,
                "rol_nombre": usuario.rol.nombre,
                "recinto_id": usuario.recinto_id,
            },
        }
    )


@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    usuario = usuario_actual()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    return jsonify(
        {
            "id": usuario.id,
            "ci": usuario.ci,
            "nombre_completo": usuario.nombre_completo,
            "email": usuario.email,
            "rol_id": usuario.rol_id,
            "rol_nombre": usuario.rol.nombre,
            "recinto_id": usuario.recinto_id,
            "recinto_nombre": usuario.recinto.nombre if usuario.recinto else None,
        }
    )


# ──────────────────────────────────────────────────────────────
#  Gestión de usuarios (solo ADMIN)
# ──────────────────────────────────────────────────────────────

@bp.route("/usuarios", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN)
def listar_usuarios():
    rol_id = request.args.get("rol_id", type=int)
    usuarios = auth_service.listar_usuarios(rol_id=rol_id)
    return jsonify(
        [
            {
                "id": u.id,
                "ci": u.ci,
                "nombre_completo": u.nombre_completo,
                "email": u.email,
                "rol_id": u.rol_id,
                "rol_nombre": u.rol.nombre,
                "recinto_id": u.recinto_id,
                "recinto_nombre": u.recinto.nombre if u.recinto else None,
                "activo": u.activo,
            }
            for u in usuarios
        ]
    )


@bp.route("/usuarios", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def crear_usuario():
    data = request.get_json(silent=True) or {}

    requeridos = ("ci", "nombres", "apellidos", "email", "password", "rol_id")
    faltantes = [c for c in requeridos if not data.get(c)]
    if faltantes:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(faltantes)}"}), 400

    try:
        usuario = auth_service.crear_usuario(
            ci=data["ci"],
            nombres=data["nombres"],
            apellidos=data["apellidos"],
            email=data["email"],
            password=data["password"],
            rol_id=data["rol_id"],
            recinto_id=data.get("recinto_id"),
            creado_por=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except auth_service.AuthError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": usuario.id, "mensaje": "Usuario creado correctamente"}), 201


@bp.route("/usuarios/<int:usuario_id>/password", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def cambiar_password(usuario_id):
    data = request.get_json(silent=True) or {}
    nueva = data.get("password")
    if not nueva or len(nueva) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400

    try:
        auth_service.cambiar_password(
            usuario_id=usuario_id,
            nueva_password=nueva,
            cambiado_por=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except auth_service.AuthError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Contraseña actualizada"})


@bp.route("/usuarios/<int:usuario_id>", methods=["DELETE"])
@rol_requerido(Usuario.ROL_ADMIN)
def eliminar_usuario(usuario_id):
    """
    El administrador puede eliminar (desactivar) a operadores u otros
    administradores, siempre con justificación obligatoria.
    """
    data = request.get_json(silent=True) or {}
    justificacion = data.get("justificacion", "")

    try:
        auth_service.eliminar_usuario(
            usuario_id=usuario_id,
            justificacion=justificacion,
            eliminado_por=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except auth_service.AuthError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Usuario desactivado correctamente"})
