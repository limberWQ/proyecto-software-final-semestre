from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.models import Usuario, Departamento, Recinto
from app.services import election_service
from app.decorators import rol_requerido, jwt_requerido

bp = Blueprint("elections", __name__, url_prefix="/api/elecciones")


def _serializar(eleccion):
    return {
        "id": eleccion.id,
        "codigo": eleccion.codigo,
        "titulo": eleccion.titulo,
        "descripcion": eleccion.descripcion,
        "tipo": eleccion.tipo,
        "estado": eleccion.estado,
        "departamento_id": eleccion.departamento_id,
        "departamento_nombre": eleccion.departamento.nombre,
        "fecha_inicio": eleccion.fecha_inicio.isoformat(),
        "fecha_fin": eleccion.fecha_fin.isoformat() if eleccion.fecha_fin else None,
        "created_at": eleccion.created_at.isoformat(),
        "tiene_clave_publica": bool(eleccion.clave_publica_pem),
    }


@bp.route("", methods=["GET"])
@jwt_requerido
def listar():
    departamento_id = request.args.get("departamento_id", type=int)
    elecciones = election_service.listar_elecciones(departamento_id=departamento_id)
    return jsonify([_serializar(e) for e in elecciones])


@bp.route("/<int:eleccion_id>", methods=["GET"])
@jwt_requerido
def obtener(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(_serializar(eleccion))


@bp.route("", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def crear():
    """
    Crea una elección presidencial PARA UN DEPARTAMENTO. Cada departamento
    maneja su propia elección de forma independiente.
    """
    data = request.get_json(silent=True) or {}

    requeridos = ("codigo", "titulo", "tipo", "departamento_id", "fecha_inicio")
    faltantes = [c for c in requeridos if not data.get(c)]
    if faltantes:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(faltantes)}"}), 400

    from datetime import datetime
    try:
        fecha_inicio = datetime.fromisoformat(data["fecha_inicio"])
        fecha_fin = datetime.fromisoformat(data["fecha_fin"]) if data.get("fecha_fin") else None
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido (use ISO 8601)"}), 400

    try:
        eleccion = election_service.crear_eleccion(
            codigo=data["codigo"],
            titulo=data["titulo"],
            descripcion=data.get("descripcion"),
            tipo=data["tipo"],
            departamento_id=data["departamento_id"],
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except election_service.ElectionError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": eleccion.id, "mensaje": "Elección creada correctamente"}), 201


@bp.route("/<int:eleccion_id>", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def actualizar(eleccion_id):
    data = request.get_json(silent=True) or {}

    from datetime import datetime
    if "fecha_inicio" in data:
        data["fecha_inicio"] = datetime.fromisoformat(data["fecha_inicio"])
    if "fecha_fin" in data and data["fecha_fin"]:
        data["fecha_fin"] = datetime.fromisoformat(data["fecha_fin"])

    try:
        election_service.actualizar_eleccion(
            eleccion_id=eleccion_id,
            datos=data,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except election_service.ElectionError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Elección actualizada"})


@bp.route("/<int:eleccion_id>/estado", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def cambiar_estado(eleccion_id):
    """
    Botones de control: Activar / Suspender / Reanudar / Cerrar elección.
    Body: { "estado": "ACTIVA" | "SUSPENDIDA" | "CERRADA" }
    """
    data = request.get_json(silent=True) or {}
    nuevo_estado = data.get("estado")
    if not nuevo_estado:
        return jsonify({"error": "Campo 'estado' requerido"}), 400

    try:
        eleccion = election_service.cambiar_estado(
            eleccion_id=eleccion_id,
            nuevo_estado=nuevo_estado,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except election_service.ElectionError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": f"Estado actualizado a {eleccion.estado}", "estado": eleccion.estado})


@bp.route("/<int:eleccion_id>/recintos", methods=["GET"])
@jwt_requerido
def recintos_asignados(eleccion_id):
    recintos = election_service.recintos_de_eleccion(eleccion_id)
    return jsonify(
        [
            {
                "id": r.id,
                "codigo": r.codigo,
                "nombre": r.nombre,
                "municipio": r.municipio,
                "total_mesas": r.total_mesas,
            }
            for r in recintos
        ]
    )


@bp.route("/<int:eleccion_id>/recintos", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def asignar_recintos(eleccion_id):
    """Botón 'Asignar recintos a la elección'. Body: { "recinto_ids": [1,2,3] }"""
    data = request.get_json(silent=True) or {}
    recinto_ids = data.get("recinto_ids", [])

    try:
        election_service.asignar_recintos(
            eleccion_id=eleccion_id,
            recinto_ids=recinto_ids,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except election_service.ElectionError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Recintos asignados correctamente"})


# ──────────────────────────────────────────────────────────────
#  Departamentos y recintos (catálogos auxiliares)
# ──────────────────────────────────────────────────────────────

@bp.route("/departamentos", methods=["GET"])
@jwt_requerido
def listar_departamentos():
    deptos = Departamento.query.order_by(Departamento.nombre).all()
    return jsonify([{"id": d.id, "nombre": d.nombre} for d in deptos])


@bp.route("/recintos", methods=["GET"])
@jwt_requerido
def listar_recintos():
    departamento_id = request.args.get("departamento_id", type=int)
    query = Recinto.query
    if departamento_id:
        query = query.filter_by(departamento_id=departamento_id)
    recintos = query.order_by(Recinto.nombre).all()
    return jsonify(
        [
            {
                "id": r.id,
                "codigo": r.codigo,
                "nombre": r.nombre,
                "municipio": r.municipio,
                "departamento_id": r.departamento_id,
                "total_mesas": r.total_mesas,
                "activo": r.activo,
            }
            for r in recintos
        ]
    )


@bp.route("/recintos", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def crear_recinto():
    """Botón 'Agregar recinto'."""
    data = request.get_json(silent=True) or {}
    requeridos = ("codigo", "nombre", "municipio", "departamento_id")
    faltantes = [c for c in requeridos if not data.get(c)]
    if faltantes:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(faltantes)}"}), 400

    from app.extensions import db
    if Recinto.query.filter_by(codigo=data["codigo"]).first():
        return jsonify({"error": "Ya existe un recinto con ese código"}), 400

    recinto = Recinto(
        codigo=data["codigo"],
        nombre=data["nombre"],
        direccion=data.get("direccion"),
        municipio=data["municipio"],
        departamento_id=data["departamento_id"],
        total_mesas=data.get("total_mesas", 1),
        activo=True,
    )
    db.session.add(recinto)
    db.session.commit()

    return jsonify({"id": recinto.id, "mensaje": "Recinto creado correctamente"}), 201
