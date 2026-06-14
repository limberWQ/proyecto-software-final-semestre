from flask import Blueprint, request, jsonify

from app.models import SesionKiosco, Eleccion
from app.services import vote_service, candidato_service

bp = Blueprint("votes", __name__, url_prefix="/api/votacion")


@bp.route("/papeleta/<int:sesion_id>", methods=["GET"])
def papeleta(sesion_id):
    """
    Devuelve la papeleta (lista de candidatos presidenciales) para la
    sesión de kiosco activa. El celular llama esto cuando el estado del
    kiosco indica habilitado=true.
    """
    sesion = SesionKiosco.query.get(sesion_id)
    if not sesion:
        return jsonify({"error": "Sesión no encontrada"}), 404

    if not sesion.esta_vigente:
        return jsonify({"error": "La sesión de votación expiró", "kiosco_no_habilitado": True}), 410

    eleccion = Eleccion.query.get(sesion.padron.eleccion_id)
    candidatos = candidato_service.listar_candidatos(eleccion.id, solo_activos=True)

    return jsonify(
        {
            "eleccion": {
                "id": eleccion.id,
                "titulo": eleccion.titulo,
            },
            "segundos_restantes": sesion.segundos_restantes,
            "candidatos": [
                {
                    "id": c.id,
                    "numero_lista": c.numero_lista,
                    "sigla_partido": c.sigla_partido,
                    "nombre_partido": c.nombre_partido,
                    "nombre_completo": c.nombre_completo,
                    "formula_completa": c.formula_completa,
                    "logo_partido": c.logo_partido,
                    "foto_candidato": c.foto_candidato,
                    "color_partido": c.color_partido,
                }
                for c in candidatos
            ],
        }
    )


@bp.route("/emitir", methods=["POST"])
def emitir():
    """
    Emite el voto desde el kiosco (celular).

    Body:
      {
        "sesion_id": int,
        "tipo_voto": "VALIDO" | "BLANCO" | "NULO",
        "candidato_id": int  (requerido si tipo_voto == "VALIDO")
      }

    El frontend del kiosco debe mostrar primero un modal de confirmación
    ("¿Confirmar voto por <candidato>?") antes de llamar a este endpoint,
    ya que esta acción es irreversible.
    """
    data = request.get_json(silent=True) or {}
    sesion_id = data.get("sesion_id")
    tipo_voto = data.get("tipo_voto", "VALIDO")
    candidato_id = data.get("candidato_id")

    if not sesion_id:
        return jsonify({"error": "sesion_id es requerido"}), 400

    try:
        resultado = vote_service.emitir_voto(
            sesion_id=sesion_id,
            candidato_id=candidato_id,
            tipo_voto=tipo_voto,
            ip=request.remote_addr,
        )
    except vote_service.VoteError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "mensaje": "Voto registrado correctamente. Gracias por votar.",
            **resultado,
        }
    )
