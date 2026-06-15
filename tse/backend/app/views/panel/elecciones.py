from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, g

from app.models import Usuario, Departamento, Recinto, Candidato
from app.services import election_service, candidato_service, padron_service, segip_service
from app.views.web_decorators import rol_web_requerido
from app.views.panel import bp


@bp.route("/elecciones")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def elecciones():
    departamento_id = request.args.get("departamento_id", type=int)
    estado = request.args.get("estado")

    lista = election_service.listar_elecciones(departamento_id=departamento_id)
    if estado:
        lista = [e for e in lista if e.estado == estado]

    departamentos = Departamento.query.order_by(Departamento.nombre).all()

    return render_template(
        "admin/election_list.html",
        usuario=g.usuario,
        active="elecciones",
        elecciones=lista,
        departamentos=departamentos,
        filtro_departamento=departamento_id,
        filtro_estado=estado,
    )


@bp.route("/elecciones/nueva", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def nueva_eleccion():
    departamentos = Departamento.query.order_by(Departamento.nombre).all()

    if request.method == "GET":
        return render_template(
            "admin/election_form.html",
            usuario=g.usuario,
            active="elecciones",
            departamentos=departamentos,
        )

    data = request.form
    try:
        fecha_inicio = datetime.fromisoformat(data["fecha_inicio"])
        fecha_fin = datetime.fromisoformat(data["fecha_fin"]) if data.get("fecha_fin") else None
    except (ValueError, KeyError):
        flash("Formato de fecha inválido.", "error")
        return redirect(url_for("panel.nueva_eleccion"))

    try:
        eleccion = election_service.crear_eleccion(
            codigo=data["codigo"].strip(),
            titulo=data["titulo"].strip(),
            descripcion=data.get("descripcion", "").strip() or None,
            tipo=data["tipo"],
            departamento_id=int(data["departamento_id"]),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.nueva_eleccion"))

    flash(f"Elección '{eleccion.titulo}' creada en estado Configuración.", "success")
    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion.id))


@bp.route("/elecciones/<int:eleccion_id>")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def detalle_eleccion(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.elecciones"))

    candidatos = candidato_service.listar_candidatos(eleccion_id, solo_activos=False)
    recintos_asignados = election_service.recintos_de_eleccion(eleccion_id)
    recintos_departamento = Recinto.query.filter_by(departamento_id=eleccion.departamento_id, activo=True).all()

    total_padron = len(padron_service.listar_padron(eleccion_id))

    return render_template(
        "admin/dashboard_eleccion.html",
        usuario=g.usuario,
        active="elecciones",
        eleccion=eleccion,
        candidatos=candidatos,
        recintos_asignados=recintos_asignados,
        recintos_departamento=recintos_departamento,
        total_padron=total_padron,
        editable=(eleccion.estado == "CONFIGURACION"),
    )


@bp.route("/elecciones/<int:eleccion_id>/editar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def editar_eleccion(eleccion_id):
    """
    Guarda cambios generales (título, descripción, fechas, recintos
    asignados). Solo permitido mientras la elección está en CONFIGURACION
    (el servicio valida esto y rechaza si ya está en curso).
    """
    data = request.form
    datos = {}

    if data.get("titulo"):
        datos["titulo"] = data["titulo"].strip()
    if "descripcion" in data:
        datos["descripcion"] = data.get("descripcion", "").strip() or None
    if data.get("fecha_inicio"):
        try:
            datos["fecha_inicio"] = datetime.fromisoformat(data["fecha_inicio"])
        except ValueError:
            flash("Fecha de inicio inválida.", "error")
            return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))
    if data.get("fecha_fin"):
        try:
            datos["fecha_fin"] = datetime.fromisoformat(data["fecha_fin"])
        except ValueError:
            flash("Fecha de fin inválida.", "error")
            return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))

    try:
        if datos:
            election_service.actualizar_eleccion(
                eleccion_id=eleccion_id, datos=datos, usuario_id=g.usuario["id"], ip=request.remote_addr
            )

        recinto_ids = request.form.getlist("recinto_ids", type=int)
        if recinto_ids:
            election_service.asignar_recintos(
                eleccion_id=eleccion_id, recinto_ids=recinto_ids, usuario_id=g.usuario["id"], ip=request.remote_addr
            )
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))

    flash("Elección actualizada correctamente.", "success")
    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))


@bp.route("/elecciones/<int:eleccion_id>/estado", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def cambiar_estado_eleccion(eleccion_id):
    """
    Botón 'Habilitar elección' (CONFIGURACION -> ACTIVA) y controles
    de Suspender / Reanudar / Cerrar. Una vez ACTIVA, la edición de
    datos generales queda bloqueada (lo valida election_service).
    """
    nuevo_estado = request.form.get("estado")

    try:
        eleccion = election_service.cambiar_estado(
            eleccion_id=eleccion_id, nuevo_estado=nuevo_estado, usuario_id=g.usuario["id"], ip=request.remote_addr
        )
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))

    mensajes = {
        "ACTIVA": "La elección fue habilitada y ya está en curso.",
        "SUSPENDIDA": "La elección fue suspendida.",
        "CERRADA": "La elección fue cerrada.",
    }
    flash(mensajes.get(eleccion.estado, "Estado actualizado."), "success")
    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))


# ──────────────────────────────────────────────────────────────
#  Candidatos (dentro de una elección, solo en CONFIGURACION)
# ──────────────────────────────────────────────────────────────

@bp.route("/elecciones/<int:eleccion_id>/candidatos/nuevo", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def nuevo_candidato(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.elecciones"))

    if request.method == "GET":
        return render_template(
            "admin/candidates/candidate_form.html",
            usuario=g.usuario,
            active="elecciones",
            eleccion=eleccion,
        )

    data = request.form
    try:
        candidato_service.crear_candidato(
            eleccion_id=eleccion_id,
            datos={
                "numero_lista": int(data["numero_lista"]),
                "sigla_partido": data["sigla_partido"].strip(),
                "nombre_partido": data.get("nombre_partido", "").strip() or None,
                "nombres": data["nombres"].strip(),
                "apellido_paterno": data["apellido_paterno"].strip(),
                "apellido_materno": data.get("apellido_materno", "").strip() or None,
                "formula_nombres": data.get("formula_nombres", "").strip() or None,
                "formula_apellido_paterno": data.get("formula_apellido_paterno", "").strip() or None,
                "color_partido": data.get("color_partido", "").strip() or None,
                "propuesta_breve": data.get("propuesta_breve", "").strip() or None,
            },
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
    except candidato_service.CandidatoError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.nuevo_candidato", eleccion_id=eleccion_id))

    flash("Candidato agregado correctamente.", "success")
    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))


@bp.route("/elecciones/<int:eleccion_id>/candidatos/<int:candidato_id>/editar", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def editar_candidato(eleccion_id, candidato_id):
    candidato = Candidato.query.get(candidato_id)
    if not candidato or candidato.eleccion_id != eleccion_id:
        flash("Candidato no encontrado.", "error")
        return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))

    if request.method == "GET":
        return render_template(
            "admin/candidates/candidate_edit_form.html",
            usuario=g.usuario,
            active="elecciones",
            eleccion=candidato.eleccion,
            candidato=candidato,
        )

    data = request.form
    try:
        candidato_service.actualizar_candidato(
            candidato_id=candidato_id,
            datos={
                "sigla_partido": data["sigla_partido"].strip(),
                "nombre_partido": data.get("nombre_partido", "").strip() or None,
                "nombres": data["nombres"].strip(),
                "apellido_paterno": data["apellido_paterno"].strip(),
                "apellido_materno": data.get("apellido_materno", "").strip() or None,
                "formula_nombres": data.get("formula_nombres", "").strip() or None,
                "formula_apellido_paterno": data.get("formula_apellido_paterno", "").strip() or None,
                "color_partido": data.get("color_partido", "").strip() or None,
                "propuesta_breve": data.get("propuesta_breve", "").strip() or None,
                "activo": "activo" in data,
            },
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
    except candidato_service.CandidatoError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.editar_candidato", eleccion_id=eleccion_id, candidato_id=candidato_id))

    flash("Candidato actualizado correctamente.", "success")
    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))


@bp.route("/elecciones/<int:eleccion_id>/candidatos/<int:candidato_id>/eliminar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def eliminar_candidato(eleccion_id, candidato_id):
    try:
        candidato_service.eliminar_candidato(
            candidato_id=candidato_id, usuario_id=g.usuario["id"], ip=request.remote_addr
        )
    except candidato_service.CandidatoError as e:
        flash(str(e), "error")
    else:
        flash("Candidato eliminado.", "success")

    return redirect(url_for("panel.detalle_eleccion", eleccion_id=eleccion_id))


# ──────────────────────────────────────────────────────────────
#  Padrón de una elección (botones consultar SEGIP / actualizar)
# ──────────────────────────────────────────────────────────────

@bp.route("/elecciones/<int:eleccion_id>/padron")
@rol_web_requerido(Usuario.ROL_ADMIN, Usuario.ROL_AUDITOR)
def padron_eleccion(eleccion_id):
    try:
        eleccion = election_service.obtener_eleccion(eleccion_id)
    except election_service.ElectionError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.elecciones"))

    filtro = request.args.get("filtro", "todos")  # todos | votaron | no_votaron
    padron = padron_service.listar_padron(eleccion_id)

    if filtro == "votaron":
        padron = [p for p in padron if p.ya_voto]
    elif filtro == "no_votaron":
        padron = [p for p in padron if not p.ya_voto]

    total = len(padron_service.listar_padron(eleccion_id))
    total_votaron = sum(1 for p in padron_service.listar_padron(eleccion_id) if p.ya_voto)

    es_auditor = g.usuario["rol_id"] == Usuario.ROL_AUDITOR

    return render_template(
        "admin/padron.html",
        usuario=g.usuario,
        active="elecciones" if es_auditor else "padron",
        eleccion=eleccion,
        padron=padron,
        filtro=filtro,
        total=total,
        total_votaron=total_votaron,
        total_no_votaron=total - total_votaron,
        es_auditor=es_auditor,
    )


@bp.route("/elecciones/<int:eleccion_id>/padron/construir", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def construir_padron(eleccion_id):
    """Botón 'Consultar y agregar usuarios habilitados para las elecciones'."""
    try:
        resumen = padron_service.construir_padron(
            eleccion_id=eleccion_id, usuario_id=g.usuario["id"], ip=request.remote_addr
        )
    except padron_service.PadronError as e:
        flash(str(e), "error")
    except segip_service.SegipError as e:
        flash(f"No se pudo conectar con SEGIP: {e}", "error")
    else:
        flash(
            f"Padrón actualizado: {resumen['agregados']} agregados, "
            f"{resumen['rechazados']} no cumplen requisitos, "
            f"{resumen['omitidos_existentes']} ya estaban registrados.",
            "success",
        )

    return redirect(url_for("panel.padron_eleccion", eleccion_id=eleccion_id))

@bp.route("/elecciones/<int:eleccion_id>/padron/distribuir", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def distribuir_padron(eleccion_id):
    try:
        resumen = padron_service.distribuir_padron(
            eleccion_id=eleccion_id,
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
        flash(
            f"Distribución completada: {resumen['asignados']} asignados, "
            f"{resumen['sin_recintos_disponibles']} sin recinto disponible.",
            "success",
        )
    except padron_service.PadronError as e:
        flash(str(e), "error")
    return redirect(url_for("panel.padron_eleccion", eleccion_id=eleccion_id))

@bp.route("/elecciones/<int:eleccion_id>/padron/actualizar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def actualizar_padron(eleccion_id):
    """Botón 'Actualizar padrón' (sincroniza con SEGIP)."""
    try:
        resumen = padron_service.actualizar_padron(
            eleccion_id=eleccion_id, usuario_id=g.usuario["id"], ip=request.remote_addr
        )
    except padron_service.PadronError as e:
        flash(str(e), "error")
    except segip_service.SegipError as e:
        flash(f"No se pudo conectar con SEGIP: {e}", "error")
    else:
        flash(
            f"Padrón sincronizado: {resumen['agregados']} nuevos, "
            f"{resumen['inhabilitados']} inhabilitados, "
            f"{resumen['rehabilitados']} rehabilitados.",
            "success",
        )

    return redirect(url_for("panel.padron_eleccion", eleccion_id=eleccion_id))


@bp.route("/elecciones/<int:eleccion_id>/padron/<int:padron_id>/asignar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def asignar_recinto_padron(eleccion_id, padron_id):
    recinto_id = request.form.get("recinto_id", type=int)
    mesa_numero = request.form.get("mesa_numero", type=int)

    if not recinto_id or not mesa_numero:
        flash("Selecciona un recinto y un número de mesa.", "error")
        return redirect(url_for("panel.padron_eleccion", eleccion_id=eleccion_id))

    try:
        padron_service.asignar_recinto(
            padron_id=padron_id,
            recinto_id=recinto_id,
            mesa_numero=mesa_numero,
            usuario_id=g.usuario["id"],
            ip=request.remote_addr,
        )
    except padron_service.PadronError as e:
        flash(str(e), "error")
    else:
        flash("Recinto y mesa asignados correctamente.", "success")

    return redirect(url_for("panel.padron_eleccion", eleccion_id=eleccion_id))
