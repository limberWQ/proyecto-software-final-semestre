from datetime import datetime
from app.extensions import db


class BloqueIndex(db.Model):
    """
    Índice en BD de los bloques de la blockchain (chain.json es la fuente
    de verdad; esta tabla permite consultas SQL rápidas para auditoría).
    """

    __tablename__ = "blockchain_bloques"

    id = db.Column(db.Integer, primary_key=True)
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"), nullable=False)
    block_index = db.Column(db.Integer, nullable=False)
    prev_hash = db.Column(db.String(64), nullable=False)
    block_hash = db.Column(db.String(64), nullable=False, unique=True)
    merkle_root = db.Column(db.String(64), nullable=False)
    total_tx = db.Column(db.Integer, nullable=False, default=0)
    nonce = db.Column(db.Integer, nullable=False, default=0)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("eleccion_id", "block_index", name="uq_block_index_eleccion"),
    )

    def __repr__(self):
        return f"<BloqueIndex eleccion={self.eleccion_id} idx={self.block_index}>"
