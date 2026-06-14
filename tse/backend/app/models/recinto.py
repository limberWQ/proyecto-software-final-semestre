from datetime import datetime
from app.extensions import db


class Departamento(db.Model):
    __tablename__ = "departamentos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return f"<Departamento {self.nombre}>"


class Recinto(db.Model):
    __tablename__ = "recintos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False, unique=True)
    nombre = db.Column(db.String(150), nullable=False)
    direccion = db.Column(db.String(200))
    municipio = db.Column(db.String(80), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=False)
    total_mesas = db.Column(db.Integer, nullable=False, default=1)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    departamento = db.relationship("Departamento", backref="recintos", lazy=True)
    kioscos = db.relationship("Kiosco", backref="recinto", lazy=True)

    def __repr__(self):
        return f"<Recinto {self.codigo} - {self.nombre}>"


class Kiosco(db.Model):
    __tablename__ = "kioscos"

    id = db.Column(db.Integer, primary_key=True)
    recinto_id = db.Column(db.Integer, db.ForeignKey("recintos.id"), nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    # Código fijo que se ingresa en el celular para vincularlo a este kiosco
    codigo_vinculacion = db.Column(db.String(20), nullable=False, unique=True)
    ip_local = db.Column(db.String(15))
    activo = db.Column(db.Boolean, nullable=False, default=True)
    ultimo_uso = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Kiosco {self.nombre} (recinto={self.recinto_id})>"


class RecintoEleccion(db.Model):
    """Tabla intermedia N:M entre recintos y elecciones."""

    __tablename__ = "recintos_elecciones"

    recinto_id = db.Column(db.Integer, db.ForeignKey("recintos.id"), primary_key=True)
    eleccion_id = db.Column(db.Integer, db.ForeignKey("elecciones.id"), primary_key=True)
