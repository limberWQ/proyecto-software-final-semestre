from datetime import datetime
from app.extensions import db


class Eleccion(db.Model):
    __tablename__ = "elecciones"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    tipo = db.Column(
        db.Enum("PRESIDENCIAL", "MUNICIPAL", "DEPARTAMENTAL", "REFERENDUM", "ASAMBLEA"),
        nullable=False,
    )
    estado = db.Column(
        db.Enum("CONFIGURACION", "ACTIVA", "SUSPENDIDA", "CERRADA"),
        nullable=False,
        default="CONFIGURACION",
    )
    # Departamento al que corresponde esta elección (cada departamento
    # tiene su propia elección presidencial para control independiente).
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=False)

    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin = db.Column(db.DateTime)

    clave_publica_pem = db.Column(db.Text)
    clave_privada_pem = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    departamento = db.relationship("Departamento", backref="elecciones", lazy=True)
    creador = db.relationship("Usuario", backref="elecciones_creadas", lazy=True)
    candidatos = db.relationship("Candidato", backref="eleccion", lazy=True, cascade="all, delete-orphan")

    @property
    def esta_activa(self):
        return self.estado == "ACTIVA"

    def __repr__(self):
        return f"<Eleccion {self.codigo} - {self.titulo} ({self.estado})>"
