from datetime import datetime
from app.extensions import db


class Conteo(db.Model):
    """
    Conteo en tiempo real por candidato (y BLANCO/NULO).

    IMPORTANTE: como los votos están cifrados con RSA (clave pública de
    la elección) y solo se descifran al cerrar la elección con la clave
    privada, este conteo NO refleja preferencias por candidato mientras
    la elección está ACTIVA. Mientras está activa, se actualiza únicamente
    el conteo agregado de "votos emitidos" (participación) en tiempo real;
    el detalle por candidato se calcula y persiste al CERRAR la elección
    (conteo_service.cerrar_y_contar).
    """

    __tablename__ = "conteos"

    id = db.Column(db.Integer, primary_key=True)
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"), nullable=False)
    candidato_id = db.Column(db.Integer, db.ForeignKey("candidatos.id"))
    tipo = db.Column(db.Enum("VALIDO", "BLANCO", "NULO"), nullable=False)
    total_votos = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("eleccion_id", "candidato_id", "tipo", name="uq_conteo"),
    )

    candidato = db.relationship("Candidato", lazy=True)

    def __repr__(self):
        return f"<Conteo eleccion={self.eleccion_id} candidato={self.candidato_id} tipo={self.tipo} total={self.total_votos}>"
