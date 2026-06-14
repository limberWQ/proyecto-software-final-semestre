from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Departamento(db.Model):
    __tablename__ = "departamentos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)


class Ciudadano(db.Model):
    __tablename__ = "ciudadanos"

    id = db.Column(db.Integer, primary_key=True)
    ci = db.Column(db.String(12), nullable=False, unique=True)
    complemento = db.Column(db.String(4))
    nombres = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(100), nullable=False)
    apellido_materno = db.Column(db.String(100))
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    lugar_nacimiento = db.Column(db.String(120))
    sexo = db.Column(db.Enum('M', 'F'), nullable=False)
    estado_civil = db.Column(db.Enum('SOLTERO', 'CASADO', 'DIVORCIADO', 'VIUDO', 'UNION_LIBRE'))
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'), nullable=False)
    municipio = db.Column(db.String(80))
    domicilio = db.Column(db.String(200))
    vivo = db.Column(db.Boolean, nullable=False, default=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    observaciones = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    departamento = db.relationship('Departamento', backref='ciudadanos', lazy=True)


class Biometria(db.Model):
    __tablename__ = "biometria"

    ciudadano_id = db.Column(db.ForeignKey('ciudadanos.id'), primary_key=True)
    foto_hash = db.Column(db.String(64), nullable=False)
    huella_hash = db.Column(db.String(64))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    ciudadano = db.relationship('Ciudadano', backref=db.backref('biometria', uselist=False))


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    sistema = db.Column(db.String(50), nullable=False)
    api_key_hash = db.Column(db.String(64), nullable=False, unique=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
