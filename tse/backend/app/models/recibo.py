from datetime import datetime
from app.extensions import db


class Recibo(db.Model):
    __tablename__ = "recibos"

    id = db.Column(db.Integer, primary_key=True)
    padron_id = db.Column(db.Integer, db.ForeignKey("padron_electoral.id"), nullable=False)
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"), nullable=False)
    codigo_recibo = db.Column(db.String(32), nullable=False, unique=True)
    block_hash = db.Column(db.String(64), nullable=False)
    impreso = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("padron_id", "eleccion_id", name="uq_padron_eleccion"),
    )

    def __repr__(self):
        return f"<Recibo {self.codigo_recibo}>"
