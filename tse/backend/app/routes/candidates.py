from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.models import Usuario
from app.services import candidato_service
from app.decorators import rol_requerido, jwt_requerido

bp = Blueprint("candidates", __name__, url_prefix="/api/elecciones/<int:eleccion_id>/candidatos")


def _serializar(c):
    return {
        "id": c.id,
        "numero_lista": c.numero_lista,
        "sigla_partido": c.sigla_partido,
        "nombre_partido": c.nombre_partido,
        "nombres": c.nombres,
        "apellido_paterno": c.apellido_paterno,
        "apellido_materno": c.apellido_materno,
        "nombre_completo": c.nombre_completo,
        "formula_completa": c.formula_completa,
        "logo_partido": c.logo_partido,
        "foto_candidato": c.foto_candidato,
        "color_partido": c.color_partido,
        "propuesta_breve": c.propuesta_breve,
        "activo": c.activo,
    }


@bp.route("", methods=["GET"])
@jwt_requerido
def listar(eleccion_id):
    solo_activos = request.args.get("solo_activos", "true").lower() != "false"
    candidatos = candidato_service.listar_candidatos(eleccion_id, solo_activos=solo_activos)
    return jsonify([_serializar(c) for c in candidatos])


@bp.route("", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def crear(eleccion_id):
    """Botón 'Agregar candidato'."""
    data = request.get_json(silent=True) or {}

    requeridos = ("numero_lista", "sigla_partido", "nombres", "apellido_paterno")
    faltantes = [c for c in requeridos if not data.get(c)]
    if faltantes:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(faltantes)}"}), 400

    try:
        candidato = candidato_service.crear_candidato(
            eleccion_id=eleccion_id,
            datos=data,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except candidato_service.CandidatoError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": candidato.id, "mensaje": "Candidato agregado correctamente"}), 201


@bp.route("/<int:candidato_id>", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def actualizar(eleccion_id, candidato_id):
    """Botón 'Editar candidato'."""
    data = request.get_json(silent=True) or {}

    try:
        candidato_service.actualizar_candidato(
            candidato_id=candidato_id,
            datos=data,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except candidato_service.CandidatoError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Candidato actualizado correctamente"})


@bp.route("/<int:candidato_id>", methods=["DELETE"])
@rol_requerido(Usuario.ROL_ADMIN)
def eliminar(eleccion_id, candidato_id):
    """Botón 'Eliminar candidato'."""
    try:
        candidato_service.eliminar_candidato(
            candidato_id=candidato_id,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except candidato_service.CandidatoError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Candidato eliminado correctamente"})
