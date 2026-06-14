import hashlib
from datetime import datetime

from app.extensions import db
from app.models import AuditLog


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def registrar_evento(
    usuario_id: int | None,
    accion: str,
    descripcion: str | None = None,
    eleccion_id: int | None = None,
    ip: str | None = None,
) -> AuditLog:
    """
    Registra un evento en el log de auditoría con hash de integridad.
    El hash permite detectar si un registro fue alterado posteriormente
    (no forma parte de la blockchain, es un log administrativo aparte).
    """
    created_at = datetime.utcnow()
    ip_hash = _hash_ip(ip)

    hash_integridad = AuditLog.calcular_hash(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion=accion,
        descripcion=descripcion,
        ip_hash=ip_hash,
        created_at=created_at,
    )

    log = AuditLog(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion=accion,
        descripcion=descripcion,
        ip_hash=ip_hash,
        hash_integridad=hash_integridad,
        created_at=created_at,
    )
    db.session.add(log)
    db.session.commit()
    return log


def verificar_integridad_log(log: AuditLog) -> bool:
    """Recalcula el hash de un registro y lo compara con el almacenado."""
    recalculado = AuditLog.calcular_hash(
        usuario_id=log.usuario_id,
        eleccion_id=log.eleccion_id,
        accion=log.accion,
        descripcion=log.descripcion,
        ip_hash=log.ip_hash,
        created_at=log.created_at,
    )
    return recalculado == log.hash_integridad


def listar_eventos(eleccion_id: int | None = None, accion: str | None = None, limite: int = 200):
    query = AuditLog.query
    if eleccion_id:
        query = query.filter_by(eleccion_id=eleccion_id)
    if accion:
        query = query.filter_by(accion=accion)
    return query.order_by(AuditLog.created_at.desc()).limit(limite).all()
