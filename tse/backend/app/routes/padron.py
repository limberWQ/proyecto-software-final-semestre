from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt

from app.models import Usuario
from app.services import padron_service, segip_service
from app.decorators import rol_requerido

bp = Blueprint("padron", __name__, url_prefix="/api/elecciones/<int:eleccion_id>/padron")


def _serializar(p):
    return {
        "id": p.id,
        "ci": p.ci,
        "nombre_completo": p.nombre_completo,
        "sexo": p.sexo,
        "fecha_nacimiento": p.fecha_nacimiento.isoformat(),
        "departamento_id": p.departamento_id,
        "recinto_id": p.recinto_id,
        "recinto_nombre": p.recinto.nombre if p.recinto else None,
        "mesa_numero": p.mesa_numero,
        "habilitado": p.habilitado,
        "motivo_inhabilitacion": p.motivo_inhabilitacion,
        "ya_voto": p.ya_voto,
        "hora_voto": p.hora_voto.isoformat() if p.hora_voto else None,
    }


@bp.route("", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_OPERADOR, Usuario.ROL_AUDITOR)
def listar(eleccion_id):
    """
    Lista el padrón. Si el usuario es AUDITOR, no se exponen nombres
    (solo CI parcial y estado), para no revelar identidades de votantes.
    """
    claims = get_jwt()
    recinto_id = request.args.get("recinto_id", type=int)

    padron = padron_service.listar_padron(eleccion_id, recinto_id=recinto_id)

    if claims.get("rol_id") == Usuario.ROL_AUDITOR:
        return jsonify(
            [
                {
                    "id": p.id,
                    "ci_parcial": p.ci[:4] + "****",
                    "recinto_id": p.recinto_id,
                    "recinto_nombre": p.recinto.nombre if p.recinto else None,
                    "mesa_numero": p.mesa_numero,
                    "habilitado": p.habilitado,
                    "ya_voto": p.ya_voto,
                }
                for p in padron
            ]
        )

    return jsonify([_serializar(p) for p in padron])


@bp.route("/construir", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def construir(eleccion_id):
    """
    Botón "Consultar y agregar usuarios habilitados para las elecciones".
    Consulta SEGIP y agrega al padrón TSE a quienes:
      - tienen 18+ años al día de la votación
      - están vivos
      - pertenecen al departamento de esta elección
    """
    try:
        resumen = padron_service.construir_padron(
            eleccion_id=eleccion_id,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except padron_service.PadronError as e:
        return jsonify({"error": str(e)}), 400
    except segip_service.SegipError as e:
        return jsonify({"error": f"Error al conectar con SEGIP: {e}"}), 502

    return jsonify(resumen)

@bp.route("/distribuir", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def distribuir(eleccion_id):
    """Botón 'Distribuir padrón en recintos y mesas'."""
    try:
        resumen = padron_service.distribuir_padron(
            eleccion_id=eleccion_id,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except padron_service.PadronError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(resumen)

@bp.route("/actualizar", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def actualizar(eleccion_id):
    """
    Botón "Actualizar padrón".
    Vuelve a consultar SEGIP: agrega nuevos elegibles e inhabilita a
    quienes el SEGIP ahora reporta como fallecidos.
    """
    try:
        resumen = padron_service.actualizar_padron(
            eleccion_id=eleccion_id,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except padron_service.PadronError as e:
        return jsonify({"error": str(e)}), 400
    except segip_service.SegipError as e:
        return jsonify({"error": f"Error al conectar con SEGIP: {e}"}), 502

    return jsonify(resumen)


@bp.route("/<int:padron_id>/recinto", methods=["PUT"])
@rol_requerido(Usuario.ROL_ADMIN)
def asignar_recinto(eleccion_id, padron_id):
    """Botón 'Asignar recinto y mesa' a un votante del padrón."""
    data = request.get_json(silent=True) or {}
    recinto_id = data.get("recinto_id")
    mesa_numero = data.get("mesa_numero")

    if not recinto_id or not mesa_numero:
        return jsonify({"error": "recinto_id y mesa_numero son requeridos"}), 400

    try:
        padron_service.asignar_recinto(
            padron_id=padron_id,
            recinto_id=recinto_id,
            mesa_numero=mesa_numero,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except padron_service.PadronError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"mensaje": "Recinto y mesa asignados correctamente"})


@bp.route("/buscar/<string:ci>", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_OPERADOR)
def buscar(eleccion_id, ci):
    """Usado por el operador (PC3) antes de habilitar el kiosco."""
    votante = padron_service.buscar_votante(eleccion_id, ci)
    if not votante:
        return jsonify({"error": "Ciudadano no encontrado en el padrón de esta elección"}), 404

    return jsonify(_serializar(votante))
