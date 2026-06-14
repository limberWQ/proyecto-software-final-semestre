import hashlib
import json
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"))
    accion = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    ip_hash = db.Column(db.String(64))
    hash_integridad = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario = db.relationship("Usuario", lazy=True)
    eleccion = db.relationship("Eleccion", lazy=True)

    @staticmethod
    def calcular_hash(usuario_id, eleccion_id, accion, descripcion, ip_hash, created_at):
        data = json.dumps(
            {
                "usuario_id": usuario_id,
                "eleccion_id": eleccion_id,
                "accion": accion,
                "descripcion": descripcion,
                "ip_hash": ip_hash,
                "created_at": created_at.isoformat() if created_at else None,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def __repr__(self):
        return f"<AuditLog {self.accion} usuario={self.usuario_id}>"
