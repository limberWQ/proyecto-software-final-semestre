import hashlib
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify

from app.extensions import db
from app.models import Usuario, PadronElectoral, Kiosco, SesionKiosco, Eleccion
from app.services import segip_service, padron_service, election_service
from app.services.audit_service import registrar_evento
from app.views.web_decorators import rol_web_requerido

bp = Blueprint("operador", __name__, url_prefix="/operador")


def _eleccion_activa_del_operador(recinto_id: int) -> Eleccion | None:
    """Devuelve la primera elección ACTIVA que incluye el recinto del operador."""
    from app.models import RecintoEleccion
    re = RecintoEleccion.query.filter_by(recinto_id=recinto_id).first()
    if not re:
        return None
    eleccion = Eleccion.query.filter_by(id=re.eleccion_id, estado="ACTIVA").first()
    return eleccion


# ── Verificar votante ─────────────────────────────────────────

@bp.route("/verificar", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_OPERADOR)
def verificar():
    recinto_id = g.usuario.get("recinto_id")
    if not recinto_id:
        flash("Tu usuario no está asignado a ningún recinto. Contacta al administrador.", "error")
        return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                               votante=None, eleccion=None)

    eleccion = _eleccion_activa_del_operador(recinto_id)
    votante = None
    ci_buscado = None

    if request.method == "POST":
        ci = request.form.get("ci", "").strip()
        ci_buscado = ci

        if not ci:
            flash("Ingresa el CI del votante.", "error")
            return redirect(url_for("operador.verificar"))

        if not eleccion:
            flash("No hay ninguna elección activa en tu recinto en este momento.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=None, eleccion=None, ci_buscado=ci_buscado)

        # 1. Verificar en SEGIP que existe y está vivo
        try:
            datos_segip = segip_service.verificar_ciudadano(ci)
        except segip_service.SegipError as e:
            flash(f"Error al consultar SEGIP: {e}", "error")
            return redirect(url_for("operador.verificar"))

        if not datos_segip:
            flash("CI no encontrado en SEGIP o ciudadano inactivo.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=None, eleccion=eleccion, ci_buscado=ci_buscado)

        if not datos_segip.get("vivo", True):
            flash("Este ciudadano figura como fallecido en SEGIP. No puede votar.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=None, eleccion=eleccion, ci_buscado=ci_buscado)

        # 2. Verificar en el padrón de la elección
        registro = padron_service.buscar_votante(eleccion.id, ci)
        if not registro:
            flash("Este CI no está en el padrón de la elección activa.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=None, eleccion=eleccion, ci_buscado=ci_buscado)

        if not registro.habilitado:
            flash(f"Votante inhabilitado: {registro.motivo_inhabilitacion or 'sin motivo registrado'}.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=registro, eleccion=eleccion, ci_buscado=ci_buscado)

        if registro.ya_voto:
            flash("Este votante ya emitió su voto en esta elección.", "error")
            return render_template("operator/verificar.html", usuario=g.usuario, active="verificar",
                                   votante=registro, eleccion=eleccion, ci_buscado=ci_buscado)

        votante = registro

    return render_template(
        "operator/verificar.html",
        usuario=g.usuario,
        active="verificar",
        votante=votante,
        eleccion=eleccion,
        ci_buscado=ci_buscado,
    )


# ── Habilitar kiosco (después de verificar al votante) ────────

@bp.route("/habilitar-kiosco", methods=["POST"])
@rol_web_requerido(Usuario.ROL_OPERADOR)
def habilitar_kiosco():
    padron_id = request.form.get("padron_id", type=int)
    kiosco_id = request.form.get("kiosco_id", type=int)

    if not padron_id or not kiosco_id:
        flash("Datos incompletos para habilitar el kiosco.", "error")
        return redirect(url_for("operador.verificar"))

    registro = PadronElectoral.query.get(padron_id)
    if not registro or registro.ya_voto or not registro.habilitado:
        flash("El votante no está habilitado o ya votó.", "error")
        return redirect(url_for("operador.verificar"))

    kiosco = Kiosco.query.get(kiosco_id)
    if not kiosco or not kiosco.activo:
        flash("Kiosco inválido o inactivo.", "error")
        return redirect(url_for("operador.verificar"))

    # Expirar sesiones anteriores vigentes de este kiosco
    sesiones_viejas = SesionKiosco.query.filter(
        SesionKiosco.kiosco_id == kiosco_id,
        SesionKiosco.estado.in_(["PENDIENTE", "ACTIVA"]),
    ).all()
    for s in sesiones_viejas:
        s.estado = "EXPIRADA"

    # Crear nueva sesión
    token_raw = f"{padron_id}:{kiosco_id}:{datetime.utcnow().isoformat()}"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()

    sesion = SesionKiosco(
        operador_id=g.usuario["id"],
        padron_id=padron_id,
        kiosco_id=kiosco_id,
        token_hash=token_hash,
        estado="PENDIENTE",
        expira_en=SesionKiosco.calcular_expiracion(),
    )
    db.session.add(sesion)
    db.session.commit()

    registrar_evento(
        g.usuario["id"],
        "KIOSCO_HABILITADO",
        f"Kiosco {kiosco.nombre} habilitado para CI {registro.ci}",
        eleccion_id=registro.eleccion_id,
        ip=request.remote_addr,
    )

    flash(f"Kiosco '{kiosco.nombre}' habilitado. El votante tiene 5 minutos para votar.", "success")
    return redirect(url_for("operador.verificar"))


# ── Vista de kiosco del operador (muestra qué kiosco tiene asignado) ──

@bp.route("/kiosco")
@rol_web_requerido(Usuario.ROL_OPERADOR)
def kiosco():
    recinto_id = g.usuario.get("recinto_id")
    if not recinto_id:
        flash("No estás asignado a ningún recinto.", "error")
        return render_template("operator/dashboard.html", usuario=g.usuario, active="kiosco",
                               kioscos=[], eleccion=None)

    kioscos = Kiosco.query.filter_by(recinto_id=recinto_id, activo=True).all()
    eleccion = _eleccion_activa_del_operador(recinto_id)

    # Estado actual de cada kiosco (sesión vigente o libre)
    estados_kiosco = {}
    for k in kioscos:
        sesion = SesionKiosco.query.filter(
            SesionKiosco.kiosco_id == k.id,
            SesionKiosco.estado.in_(["PENDIENTE", "ACTIVA"]),
        ).order_by(SesionKiosco.created_at.desc()).first()

        if sesion and sesion.esta_vigente:
            estados_kiosco[k.id] = {
                "estado": "habilitado",
                "segundos": sesion.segundos_restantes,
                "sesion_id": sesion.id,
            }
        else:
            estados_kiosco[k.id] = {"estado": "libre"}

    return render_template(
        "operator/dashboard.html",
        usuario=g.usuario,
        active="kiosco",
        kioscos=kioscos,
        eleccion=eleccion,
        estados_kiosco=estados_kiosco,
    )


# ── API de estado de kiosco (polling del celular) ─────────────

@bp.route("/kiosco/<int:kiosco_id>/estado-json")
def estado_kiosco_json(kiosco_id):
    """
    Endpoint de polling para el celular (kiosco).
    No requiere login web — el celular solo conoce el kiosco_id.
    Devuelve si hay una sesión activa y los datos para mostrar la papeleta.
    """
    kiosco = Kiosco.query.get(kiosco_id)
    if not kiosco or not kiosco.activo:
        return jsonify({"habilitado": False, "motivo": "Kiosco inactivo"})

    sesion = SesionKiosco.query.filter(
        SesionKiosco.kiosco_id == kiosco_id,
        SesionKiosco.estado.in_(["PENDIENTE", "ACTIVA"]),
    ).order_by(SesionKiosco.created_at.desc()).first()

    if not sesion or not sesion.esta_vigente:
        # Marcar como expirada si el tiempo venció
        if sesion and sesion.estado in ("PENDIENTE", "ACTIVA"):
            sesion.estado = "EXPIRADA"
            db.session.commit()
        return jsonify({"habilitado": False, "motivo": "Sin sesión activa"})

    # Marcar como ACTIVA al primer poll del celular
    if sesion.estado == "PENDIENTE":
        sesion.estado = "ACTIVA"
        db.session.commit()

    padron = sesion.padron
    eleccion = Eleccion.query.get(padron.eleccion_id)

    candidatos = [
        {
            "id": c.id,
            "numero_lista": c.numero_lista,
            "sigla_partido": c.sigla_partido,
            "nombre_partido": c.nombre_partido,
            "nombre_completo": c.nombre_completo,
            "formula_completa": c.formula_completa,
            "color_partido": c.color_partido or "#2b2b2b",
            "foto_candidato": c.foto_candidato,
            "logo_partido": c.logo_partido,
        }
        for c in eleccion.candidatos
        if c.activo
    ]

    return jsonify({
        "habilitado": True,
        "sesion_id": sesion.id,
        "token": sesion.token_hash[:16],  # fragmento para el celular (no el hash completo)
        "segundos_restantes": sesion.segundos_restantes,
        "eleccion": {"id": eleccion.id, "titulo": eleccion.titulo},
        "candidatos": candidatos,
    })
