from flask import Blueprint, request, jsonify

from app.models import Usuario, Recibo
from app.blockchain.chain import Blockchain
from app.blockchain import node_sync
from app.services import audit_service
from app.decorators import rol_requerido

bp = Blueprint("audit", __name__, url_prefix="/api")


# ──────────────────────────────────────────────────────────────
#  Cadena de bloques (auditoría pública dentro del sistema)
# ──────────────────────────────────────────────────────────────

@bp.route("/elecciones/<int:eleccion_id>/blockchain", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def cadena(eleccion_id):
    """Vista de la cadena completa para auditoría (chain.html)."""
    blockchain = Blockchain.get_instance(eleccion_id)
    return jsonify(
        {
            "eleccion_id": eleccion_id,
            "longitud": blockchain.longitud,
            "valida": blockchain.is_valid(),
            "bloques": blockchain.get_all_blocks(),
        }
    )


@bp.route("/elecciones/<int:eleccion_id>/blockchain/validar", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def validar_cadena(eleccion_id):
    """Botón 'Verificar integridad de la cadena'."""
    blockchain = Blockchain.get_instance(eleccion_id)
    return jsonify({"valida": blockchain.is_valid(), "longitud": blockchain.longitud})


@bp.route("/elecciones/<int:eleccion_id>/blockchain/sincronizar", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def sincronizar(eleccion_id):
    """Botón 'Sincronizar con otros nodos'."""
    reemplazada = node_sync.sincronizar(eleccion_id)
    blockchain = Blockchain.get_instance(eleccion_id)
    return jsonify(
        {
            "reemplazada": reemplazada,
            "longitud": blockchain.longitud,
            "valida": blockchain.is_valid(),
        }
    )


@bp.route("/nodos/estado", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def estado_nodos():
    """Panel de auditoría: estado de los 3 nodos de la red."""
    return jsonify(node_sync.estado_nodos())


# ──────────────────────────────────────────────────────────────
#  Verificación de recibo (votante o auditor)
# ──────────────────────────────────────────────────────────────

@bp.route("/recibo/<string:codigo_recibo>", methods=["GET"])
def verificar_recibo(codigo_recibo):
    """
    Verifica que un recibo de votación corresponde a un bloque real
    de la blockchain (verify_receipt.html). No requiere autenticación:
    cualquier votante puede verificar su propio recibo con el código
    que se le entregó.
    """
    recibo = Recibo.query.filter_by(codigo_recibo=codigo_recibo).first()
    if not recibo:
        return jsonify({"encontrado": False, "mensaje": "Código de recibo no encontrado"}), 404

    blockchain = Blockchain.get_instance(recibo.eleccion_id)
    bloque = blockchain.find_block_by_hash(recibo.block_hash)

    if not bloque:
        return jsonify({"encontrado": False, "mensaje": "El bloque asociado no existe en la cadena"}), 404

    return jsonify(
        {
            "encontrado": True,
            "codigo_recibo": recibo.codigo_recibo,
            "block_hash": recibo.block_hash,
            "block_index": bloque["index"],
            "timestamp": bloque["timestamp"],
            "eleccion_id": recibo.eleccion_id,
            "registrado_el": recibo.created_at.isoformat(),
        }
    )


# ──────────────────────────────────────────────────────────────
#  Logs de auditoría administrativa
# ──────────────────────────────────────────────────────────────

@bp.route("/auditoria/eventos", methods=["GET"])
@rol_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def eventos():
    eleccion_id = request.args.get("eleccion_id", type=int)
    accion = request.args.get("accion")
    lista_eventos = audit_service.listar_eventos(eleccion_id=eleccion_id, accion=accion)

    return jsonify(
        [
            {
                "id": e.id,
                "usuario_id": e.usuario_id,
                "usuario": e.usuario.nombre_completo if e.usuario else "Sistema",
                "eleccion_id": e.eleccion_id,
                "accion": e.accion,
                "descripcion": e.descripcion,
                "created_at": e.created_at.isoformat(),
                "integro": audit_service.verificar_integridad_log(e),
            }
            for e in lista_eventos
        ]
    )
