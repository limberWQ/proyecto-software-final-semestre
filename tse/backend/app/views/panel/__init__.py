from flask import Blueprint, render_template, g, jsonify
from app.models import Usuario, Eleccion, Recinto, Kiosco, PadronElectoral
from app.services import election_service
from app.views.web_decorators import rol_web_requerido

bp = Blueprint("panel", __name__, url_prefix="/panel")


@bp.route("/")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def inicio():
    elecciones = election_service.listar_elecciones()
    resumen_estados = {"CONFIGURACION": 0, "ACTIVA": 0, "SUSPENDIDA": 0, "CERRADA": 0}
    for e in elecciones:
        resumen_estados[e.estado] = resumen_estados.get(e.estado, 0) + 1
    contexto = {
        "elecciones": elecciones[:8],
        "resumen_estados": resumen_estados,
        "total_elecciones": len(elecciones),
    }
    if g.usuario["rol_id"] == Usuario.ROL_ADMIN:
        contexto["total_recintos"] = Recinto.query.count()
        contexto["total_kioscos"] = Kiosco.query.count()
        contexto["total_usuarios"] = Usuario.query.filter_by(activo=True).count()
    template = "admin/dashboard.html" if g.usuario["rol_id"] == Usuario.ROL_ADMIN else "audit/dashboard.html"
    return render_template(template, usuario=g.usuario, active="inicio", **contexto)


@bp.route("/operador")
@rol_web_requerido(Usuario.ROL_OPERADOR)
def dashboard_operador():
    recinto = Recinto.query.get(g.usuario.get("recinto_id"))
    if not recinto:
        return render_template(
            "operator/verificar.html",
            usuario=g.usuario, active="inicio",
            eleccion=None, votante=None, ci_buscado=None, kiosco_ids_ocupados=set(),
        )

    eleccion = election_service.obtener_eleccion_activa_por_recinto(recinto.id)
    if not eleccion:
        return render_template(
            "operator/verificar.html",
            usuario=g.usuario, active="inicio",
            eleccion=None, votante=None, ci_buscado=None, kiosco_ids_ocupados=set(),
        )

    query = PadronElectoral.query.filter_by(eleccion_id=eleccion.id, recinto_id=recinto.id)
    total = query.count()
    total_votaron = query.filter_by(ya_voto=True).count()

    contexto = {
        "eleccion": eleccion,
        "recinto": recinto,
        "total": total,
        "total_votaron": total_votaron,
        "total_no_votaron": total - total_votaron,
        "padron": query.all(),
    }

    return render_template(
        "operator/dashboard_inicio.html",
        usuario=g.usuario, active="inicio", **contexto,
    )


@bp.route("/api/operador/estado-recinto")
@rol_web_requerido(Usuario.ROL_OPERADOR)
def api_estado_recinto():
    recinto = Recinto.query.get(g.usuario.get("recinto_id"))
    if not recinto:
        return jsonify({"error": "Sin recinto asignado"}), 400

    eleccion = election_service.obtener_eleccion_activa_por_recinto(recinto.id)
    if not eleccion:
        return jsonify({"error": "Sin elección activa"}), 400

    query = PadronElectoral.query.filter_by(eleccion_id=eleccion.id, recinto_id=recinto.id)
    total = query.count()
    total_votaron = query.filter_by(ya_voto=True).count()

    return jsonify({
        "total_votaron": total_votaron,
        "total_no_votaron": total - total_votaron,
        "porcentaje": round(total_votaron / total * 100, 1) if total > 0 else 0,
    })


# Importar submódulos para registrar sus rutas en este blueprint
from app.views.panel import elecciones, usuarios, recintos, resultados  # noqa: E402,F401