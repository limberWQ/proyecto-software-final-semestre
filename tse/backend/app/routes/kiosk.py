import secrets

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models import Usuario, Kiosco, Recinto
from app.services import vote_service
from app.decorators import rol_requerido, jwt_requerido

bp = Blueprint("kiosk", __name__, url_prefix="/api/kioscos")


# ──────────────────────────────────────────────────────────────
#  Gestión de kioscos (ADMIN)
# ──────────────────────────────────────────────────────────────

@bp.route("", methods=["GET"])
@jwt_requerido
def listar():
    recinto_id = request.args.get("recinto_id", type=int)
    query = Kiosco.query
    if recinto_id:
        query = query.filter_by(recinto_id=recinto_id)
    kioscos = query.order_by(Kiosco.recinto_id, Kiosco.nombre).all()
    return jsonify(
        [
            {
                "id": k.id,
                "recinto_id": k.recinto_id,
                "recinto_nombre": k.recinto.nombre,
                "nombre": k.nombre,
                "codigo_vinculacion": k.codigo_vinculacion,
                "activo": k.activo,
                "ultimo_uso": k.ultimo_uso.isoformat() if k.ultimo_uso else None,
            }
            for k in kioscos
        ]
    )


@bp.route("", methods=["POST"])
@rol_requerido(Usuario.ROL_ADMIN)
def crear():
    """Botón 'Agregar kiosco' (asigna un código fijo de vinculación)."""
    data = request.get_json(silent=True) or {}
    recinto_id = data.get("recinto_id")
    nombre = data.get("nombre")

    if not recinto_id or not nombre:
        return jsonify({"error": "recinto_id y nombre son requeridos"}), 400

    recinto = Recinto.query.get(recinto_id)
    if not recinto:
        return jsonify({"error": "Recinto no encontrado"}), 404

    codigo = data.get("codigo_vinculacion") or secrets.token_hex(4).upper()

    if Kiosco.query.filter_by(codigo_vinculacion=codigo).first():
        return jsonify({"error": "El código de vinculación ya está en uso"}), 400

    kiosco = Kiosco(
        recinto_id=recinto_id,
        nombre=nombre,
        codigo_vinculacion=codigo,
        activo=True,
    )
    db.session.add(kiosco)
    db.session.commit()

    return jsonify(
        {"id": kiosco.id, "codigo_vinculacion": kiosco.codigo_vinculacion, "mensaje": "Kiosco creado"}
    ), 201


# ──────────────────────────────────────────────────────────────
#  Habilitación de mesa (operador PC3)
# ──────────────────────────────────────────────────────────────

@bp.route("/habilitar", methods=["POST"])
@rol_requerido(Usuario.ROL_OPERADOR)
def habilitar():
    """
    Botón 'Verificar y habilitar' del operador (PC3).
    Body: { "eleccion_id": int, "ci": "...", "kiosco_id": int }

    Habilita el kiosco vinculado por 5 minutos para que el votante
    emita su voto. Si el votante emite su voto antes, el kiosco
    queda libre automáticamente (sin esperar el resto del tiempo).
    """
    data = request.get_json(silent=True) or {}
    eleccion_id = data.get("eleccion_id")
    ci = data.get("ci")
    kiosco_id = data.get("kiosco_id")

    if not eleccion_id or not ci or not kiosco_id:
        return jsonify({"error": "eleccion_id, ci y kiosco_id son requeridos"}), 400

    try:
        sesion = vote_service.habilitar_kiosco(
            eleccion_id=eleccion_id,
            ci=ci,
            kiosco_id=kiosco_id,
            operador_id=int(get_jwt_identity()),
            ip=request.remote_addr,
        )
    except vote_service.VoteError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "mensaje": "Kiosco habilitado por 5 minutos",
            "sesion_id": sesion.id,
            "expira_en": sesion.expira_en.isoformat(),
            "segundos_restantes": sesion.segundos_restantes,
        }
    )


# ──────────────────────────────────────────────────────────────
#  Vinculación y estado del kiosco (celular)
#  No requieren JWT de usuario TSE: el celular se identifica
#  por el código fijo del kiosco.
# ──────────────────────────────────────────────────────────────

@bp.route("/vincular", methods=["POST"])
def vincular():
    """
    El celular ingresa el código fijo que le proporciona el operador.
    Devuelve los datos del kiosco para que el celular los guarde
    localmente (localStorage) hasta que la elección termine.
    Body: { "codigo_vinculacion": "..." }
    """
    data = request.get_json(silent=True) or {}
    codigo = data.get("codigo_vinculacion")

    if not codigo:
        return jsonify({"error": "codigo_vinculacion es requerido"}), 400

    try:
        info = vote_service.vincular_kiosco(codigo)
    except vote_service.VoteError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(info)


@bp.route("/por-codigo/<string:codigo>", methods=["GET"])
def por_codigo(codigo):
    """
    El ballot.html (celular) consulta este endpoint la primera vez
    que el usuario ingresa el código, para obtener el kiosco_id
    y guardarlo en localStorage.
    """
    kiosco = Kiosco.query.filter_by(
        codigo_vinculacion=codigo.strip().upper(), activo=True
    ).first()

    if not kiosco:
        return jsonify({"kiosco_id": None, "error": "Código inválido o kiosco inactivo"}), 404

    return jsonify({
        "kiosco_id": kiosco.id,
        "nombre": kiosco.nombre,
        "recinto": kiosco.recinto.nombre,
    })

def estado(kiosco_id):
    """
    Consultado por el celular (polling cada pocos segundos) para saber
    si debe mostrar la papeleta o el mensaje "Kiosco no habilitado".
    """
    kiosco = Kiosco.query.get(kiosco_id)
    if not kiosco:
        return jsonify({"error": "Kiosco no encontrado"}), 404

    info = vote_service.estado_kiosco(kiosco_id)
    return jsonify(info)
