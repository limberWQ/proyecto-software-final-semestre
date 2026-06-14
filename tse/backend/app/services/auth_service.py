from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import Usuario, Rol, AuditLog
from app.services.audit_service import registrar_evento


class AuthError(Exception):
    pass


def autenticar(email: str, password: str, ip: str | None = None) -> Usuario:
    """
    Verifica credenciales de un usuario TSE (admin, operador, auditor).
    Lanza AuthError si las credenciales son inválidas o el usuario está inactivo.
    """
    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not check_password_hash(usuario.password_hash, password):
        registrar_evento(
            usuario_id=None,
            accion="LOGIN_FALLIDO",
            descripcion=f"Intento de login fallido para email={email}",
            ip=ip,
        )
        raise AuthError("Credenciales inválidas")

    if not usuario.activo:
        raise AuthError("Usuario inactivo. Contacte al administrador")

    registrar_evento(
        usuario_id=usuario.id,
        accion="LOGIN_OK",
        descripcion=f"Login exitoso ({usuario.rol.nombre})",
        ip=ip,
    )
    return usuario


def crear_usuario(
    ci: str,
    nombres: str,
    apellidos: str,
    email: str,
    password: str,
    rol_id: int,
    recinto_id: int | None = None,
    creado_por: int | None = None,
    ip: str | None = None,
) -> Usuario:
    """
    Crea un nuevo usuario TSE (operador o auditor, también admin).
    Solo debe llamarse desde rutas protegidas por @rol_requerido(Usuario.ROL_ADMIN).
    """
    if Usuario.query.filter_by(ci=ci).first():
        raise AuthError("Ya existe un usuario con ese CI")
    if Usuario.query.filter_by(email=email).first():
        raise AuthError("Ya existe un usuario con ese email")

    rol = Rol.query.get(rol_id)
    if not rol:
        raise AuthError("Rol inválido")

    if rol_id == Usuario.ROL_OPERADOR and not recinto_id:
        raise AuthError("Un operador debe estar asignado a un recinto")

    usuario = Usuario(
        ci=ci,
        nombres=nombres,
        apellidos=apellidos,
        email=email,
        password_hash=generate_password_hash(password),
        rol_id=rol_id,
        recinto_id=recinto_id if rol_id == Usuario.ROL_OPERADOR else None,
        activo=True,
    )
    db.session.add(usuario)
    db.session.commit()

    registrar_evento(
        usuario_id=creado_por,
        accion="USUARIO_CREADO",
        descripcion=f"Usuario {usuario.ci} ({rol.nombre}) creado",
        ip=ip,
    )
    return usuario


def cambiar_password(usuario_id: int, nueva_password: str, cambiado_por: int, ip: str | None = None):
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        raise AuthError("Usuario no encontrado")

    usuario.password_hash = generate_password_hash(nueva_password)
    db.session.commit()

    registrar_evento(
        usuario_id=cambiado_por,
        accion="PASSWORD_CAMBIADO",
        descripcion=f"Contraseña actualizada para usuario {usuario.ci}",
        ip=ip,
    )
    return usuario


def eliminar_usuario(usuario_id: int, justificacion: str, eliminado_por: int, ip: str | None = None):
    """
    El administrador puede eliminar (desactivar) a operadores o a otros
    administradores, siempre que se justifique la acción.
    Se hace "soft delete" (activo=False) para preservar integridad
    referencial con auditoría y elecciones creadas.
    """
    if not justificacion or len(justificacion.strip()) < 10:
        raise AuthError("Debe proporcionar una justificación de al menos 10 caracteres")

    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        raise AuthError("Usuario no encontrado")

    if usuario.es_auditor:
        raise AuthError("Use la gestión de auditores para revocar permisos, no eliminar directamente")

    if usuario.id == eliminado_por:
        raise AuthError("No puede eliminarse a sí mismo")

    usuario.activo = False
    db.session.commit()

    registrar_evento(
        usuario_id=eliminado_por,
        accion="USUARIO_ELIMINADO",
        descripcion=f"Usuario {usuario.ci} ({usuario.rol.nombre}) desactivado. Justificación: {justificacion}",
        ip=ip,
    )
    return usuario


def listar_usuarios(rol_id: int | None = None):
    query = Usuario.query
    if rol_id:
        query = query.filter_by(rol_id=rol_id)
    return query.order_by(Usuario.apellidos).all()
