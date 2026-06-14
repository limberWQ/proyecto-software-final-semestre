from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.models import Usuario, PadronElectoral
from app.services import conteo_service
from app.decorators import rol_requerido, jwt_requerido

bp = Blueprint("results", __name__, url_prefix="/api/elecciones/<int:eleccion_id>/resultados")

# Blueprint adicional para endpoints públicos sin prefijo de elección
bp_pub = Blueprint("results_pub", __name__, url_prefix="/api/resultados")


@bp_pub.route("/<int:eleccion_id>/participacion", methods=["GET"])
def participacion_publica(eleccion_id):
    """
    Endpoint público para el polling de participación en tiempo real
    desde el dashboard de resultados (sin JWT — solo datos agregados).
    No revela información de candidatos ni de votantes.
    """
    total_padron = PadronElectoral.query.filter_by(eleccion_id=eleccion_id).count()
    total_votos = PadronElectoral.query.filter_by(
        eleccion_id=eleccion_id, ya_voto=True
    ).count()
    participacion = round(total_votos / total_padron * 100, 1) if total_padron else 0.0
    return jsonify({
        "eleccion_id": eleccion_id,
        "total_padron": total_padron,
        "total_votos": total_votos,
        "participacion": participacion,
    })



@bp.route("", methods=["GET"])
@jwt_requerido
def obtener(eleccion_id):
    """
    Resultados / conteo en tiempo real (web, no conteo rápido).
    Mientras la elección está ACTIVA, devuelve solo participación
    (votos emitidos / padrón total). El frontend debe hacer polling
    a este endpoint cada pocos segundos para actualizar el dashboard.
    """
    try:
        resultado = conteo_service.obtener_resultados(eleccion_id)
    except conteo_service.ConteoError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(resultado)


@bp.route("/cerrar", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def cerrar(eleccion_id):
    """
    Botón 'Cerrar elección y contar votos' (solo ADMIN).
    Descifra todos los votos de la blockchain con la clave privada
    de la elección y genera el conteo final por candidato.
    """
    try:
        resultado = conteo_service.cerrar_y_contar(
            eleccion_id=eleccion_id,
            usuario_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except conteo_service.ConteoError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(resultado)
