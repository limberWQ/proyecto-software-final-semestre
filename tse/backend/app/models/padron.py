from datetime import datetime, timedelta
from app.extensions import db


class PadronElectoral(db.Model):
    __tablename__ = "padron_electoral"

    id = db.Column(db.Integer, primary_key=True)
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"), nullable=False)
    ci = db.Column(db.String(12), nullable=False)
    complemento = db.Column(db.String(4))
    nombres = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(80), nullable=False)
    apellido_materno = db.Column(db.String(80))
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    sexo = db.Column(db.Enum("M", "F"), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=False)
    recinto_id = db.Column(db.Integer, db.ForeignKey("recintos.id"))
    mesa_numero = db.Column(db.Integer)

    habilitado = db.Column(db.Boolean, nullable=False, default=True)
    motivo_inhabilitacion = db.Column(db.String(200))

    ya_voto = db.Column(db.Boolean, nullable=False, default=False)
    hora_voto = db.Column(db.DateTime)

    habilitado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("ci", "eleccion_id", name="uq_ci_eleccion"),
    )

    recinto = db.relationship("Recinto", backref="votantes_padron", lazy=True)
    departamento = db.relationship("Departamento", lazy=True)
    operador = db.relationship("Usuario", backref="habilitaciones_padron", lazy=True)

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

    def __repr__(self):
        return f"<Padron {self.ci} - eleccion={self.eleccion_id} - voto={self.ya_voto}>"


class SesionKiosco(db.Model):
    """
    Representa la habilitación temporal (5 minutos) de un kiosco
    para que un votante específico emita su voto.

    Ciclo de vida:
      PENDIENTE  -> creada por el operador, kiosco habilitado, expira_en = now + 5min
      ACTIVA     -> el celular (kiosco) consultó el estado y está mostrando la papeleta
      COMPLETADA -> el votante emitió su voto (vote_service marca esto)
      EXPIRADA   -> pasó el tiempo sin votar; el kiosco vuelve a "no habilitado"
    """

    __tablename__ = "sesiones_kiosco"

    DURACION_MINUTOS = 5

    id = db.Column(db.Integer, primary_key=True)
    operador_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    padron_id = db.Column(db.Integer, db.ForeignKey("padron_electoral.id"), nullable=False)
    kiosco_id = db.Column(db.Integer, db.ForeignKey("kioscos.id"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    estado = db.Column(
        db.Enum("PENDIENTE", "ACTIVA", "COMPLETADA", "EXPIRADA"),
        nullable=False,
        default="PENDIENTE",
    )
    expira_en = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    operador = db.relationship("Usuario", lazy=True)
    padron = db.relationship("PadronElectoral", lazy=True)
    kiosco = db.relationship("Kiosco", lazy=True)

    @property
    def esta_vigente(self):
        return self.estado in ("PENDIENTE", "ACTIVA") and datetime.utcnow() < self.expira_en

    @property
    def segundos_restantes(self):
        delta = (self.expira_en - datetime.utcnow()).total_seconds()
        return max(0, int(delta))

    @classmethod
    def calcular_expiracion(cls):
        return datetime.utcnow() + timedelta(minutes=cls.DURACION_MINUTOS)

    def __repr__(self):
        return f"<SesionKiosco kiosco={self.kiosco_id} estado={self.estado}>"
