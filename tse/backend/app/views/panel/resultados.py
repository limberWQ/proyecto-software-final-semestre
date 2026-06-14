from flask import render_template, request, redirect, url_for, flash, g

from app.models import Usuario, Eleccion
from app.services import election_service, conteo_service, audit_service
from app.blockchain.chain import Blockchain
from app.blockchain.node_sync import estado_nodos, obtener_cadena
from app.views.web_decorators import rol_web_requerido
from app.views.panel import bp


# ── Padrón general (todas las elecciones) ─────────────────────

@bp.route("/padron")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def padron_general():
    elecciones = election_service.listar_elecciones()
    return render_template(
        "admin/padron_general.html",
        usuario=g.usuario,
        active="padron",
        elecciones=elecciones,
    )


# ── Resultados ────────────────────────────────────────────────

@bp.route("/resultados")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def resultados_general():
    elecciones = election_service.listar_elecciones()
    return render_template(
        "results/dashboard.html",
        usuario=g.usuario,
        active="resultados",
        elecciones=elecciones,
    )


@bp.route("/resultados/<int:eleccion_id>")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def resultados_eleccion(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.resultados_general"))

    from app.models import PadronElectoral
    total_padron = PadronElectoral.query.filter_by(eleccion_id=eleccion_id).count()
    total_votos = PadronElectoral.query.filter_by(eleccion_id=eleccion_id, ya_voto=True).count()
    participacion = round(total_votos / total_padron * 100, 1) if total_padron else 0

    conteos = []
    if eleccion.estado == "CERRADA":
        try:
            res = conteo_service.obtener_resultados(eleccion_id)
            conteos = res.get("conteos", [])
        except Exception:
            conteos = []

    blockchain = Blockchain.get_instance(eleccion_id)
    total_bloques = blockchain.longitud
    cadena_valida = blockchain.is_valid()

    return render_template(
        "results/eleccion_resultados.html",
        usuario=g.usuario,
        active="resultados",
        eleccion=eleccion,
        total_padron=total_padron,
        total_votos=total_votos,
        participacion=participacion,
        conteos=conteos,
        total_bloques=total_bloques,
        cadena_valida=cadena_valida,
    )


@bp.route("/resultados/<int:eleccion_id>/cerrar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def cerrar_y_contar(eleccion_id):
    """Cierra la elección y descifra/cuenta todos los votos."""
    try:
        resumen = conteo_service.cerrar_y_contar(
            eleccion_id=eleccion_id,
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
    except conteo_service.ConteoError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.resultados_eleccion", eleccion_id=eleccion_id))

    flash(
        f"Elección cerrada y conteo finalizado: "
        f"{resumen['validos']} votos válidos, "
        f"{resumen['blancos']} en blanco, "
        f"{resumen['nulos']} nulos.",
        "success",
    )
    return redirect(url_for("panel.resultados_eleccion", eleccion_id=eleccion_id))


# ── Auditoría y blockchain ────────────────────────────────────

@bp.route("/auditoria")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def auditoria():
    elecciones = election_service.listar_elecciones()
    nodos = estado_nodos()
    logs_recientes = audit_service.listar_eventos(limite=50)
    return render_template(
        "audit/chain.html",
        usuario=g.usuario,
        active="auditoria",
        elecciones=elecciones,
        nodos=nodos,
        logs=logs_recientes,
    )


@bp.route("/auditoria/eleccion/<int:eleccion_id>")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def auditoria_eleccion(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.auditoria"))

    cadena = obtener_cadena(eleccion_id)
    bloques = cadena["chain"]
    valida = cadena["valida"]

    return render_template(
        "audit/cadena_eleccion.html",
        usuario=g.usuario,
        active="auditoria",
        eleccion=eleccion,
        bloques=bloques,
        valida=valida,
        longitud=cadena["longitud"],
    )


@bp.route("/auditoria/verificar-recibo", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def verificar_recibo():
    resultado = None
    if request.method == "POST":
        codigo = request.form.get("codigo_recibo", "").strip()
        eleccion_id = request.form.get("eleccion_id", type=int)

        if codigo and eleccion_id:
            blockchain = Blockchain.get_instance(eleccion_id)
            bloque = blockchain.find_block_by_receipt(codigo)
            resultado = {
                "codigo": codigo,
                "encontrado": bloque is not None,
                "bloque": bloque,
            }

    elecciones = election_service.listar_elecciones()
    return render_template(
        "audit/verify_receipt.html",
        usuario=g.usuario,
        active="auditoria",
        elecciones=elecciones,
        resultado=resultado,
    )
