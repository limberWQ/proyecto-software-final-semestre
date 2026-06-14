from flask import Blueprint, render_template, g

from app.models import Usuario, Eleccion, Recinto, Kiosco
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


# Importar submódulos para registrar sus rutas en este blueprint
from app.views.panel import elecciones, usuarios, recintos, resultados  # noqa: E402,F401

