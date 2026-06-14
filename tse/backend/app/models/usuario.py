from datetime import datetime
from app.extensions import db


class Rol(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)
    descripcion = db.Column(db.Text)

    def __repr__(self):
        return f"<Rol {self.nombre}>"


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    ci = db.Column(db.String(12), nullable=False, unique=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    recinto_id = db.Column(db.Integer, db.ForeignKey("recintos.id"), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    rol = db.relationship("Rol", backref="usuarios", lazy=True)
    recinto = db.relationship("Recinto", backref="operadores", lazy=True)

    # Constantes de roles (deben coincidir con seed de roles en init_final.sql)
    ROL_ADMIN = 1
    ROL_OPERADOR = 2
    ROL_AUDITOR = 3

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def es_admin(self):
        return self.rol_id == Usuario.ROL_ADMIN

    @property
    def es_operador(self):
        return self.rol_id == Usuario.ROL_OPERADOR

    @property
    def es_auditor(self):
        return self.rol_id == Usuario.ROL_AUDITOR

    def __repr__(self):
        return f"<Usuario {self.ci} - {self.rol.nombre if self.rol else '?'}>"
