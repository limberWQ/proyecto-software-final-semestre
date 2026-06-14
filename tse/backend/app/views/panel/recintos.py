import secrets

from flask import render_template, request, redirect, url_for, flash, g

from app.extensions import db
from app.models import Usuario, Recinto, Kiosco, Departamento
from app.services.audit_service import registrar_evento
from app.views.web_decorators import rol_web_requerido
from app.views.panel import bp


@bp.route("/recintos")
@rol_web_requerido(Usuario.ROL_ADMIN)
def recintos():
    depto_id = request.args.get("departamento_id", type=int)
    query = Recinto.query
    if depto_id:
        query = query.filter_by(departamento_id=depto_id)
    lista = query.order_by(Recinto.nombre).all()
    departamentos = Departamento.query.order_by(Departamento.nombre).all()
    return render_template(
        "admin/recintos.html",
        usuario=g.usuario,
        active="recintos",
        recintos=lista,
        departamentos=departamentos,
        depto_filtro=depto_id,
    )


@bp.route("/recintos/nuevo", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def nuevo_recinto():
    data = request.form
    recinto = Recinto(
        codigo=data["codigo"].strip().upper(),
        nombre=data["nombre"].strip(),
        direccion=data.get("direccion", "").strip() or None,
        municipio=data["municipio"].strip(),
        departamento_id=int(data["departamento_id"]),
        total_mesas=int(data.get("total_mesas", 1)),
        activo=True,
    )
    db.session.add(recinto)
    db.session.commit()
    registrar_evento(g.usuario["id"], "RECINTO_CREADO", f"Recinto {recinto.codigo}", ip=request.remote_addr)
    flash(f"Recinto '{recinto.nombre}' creado.", "success")
    return redirect(url_for("panel.recintos"))


@bp.route("/recintos/<int:recinto_id>")
@rol_web_requerido(Usuario.ROL_ADMIN)
def detalle_recinto(recinto_id):
    recinto = Recinto.query.get_or_404(recinto_id)
    kioscos = Kiosco.query.filter_by(recinto_id=recinto_id).all()
    return render_template(
        "admin/recinto_detalle.html",
        usuario=g.usuario,
        active="recintos",
        recinto=recinto,
        kioscos=kioscos,
    )


@bp.route("/recintos/<int:recinto_id>/kioscos/nuevo", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def nuevo_kiosco(recinto_id):
    recinto = Recinto.query.get_or_404(recinto_id)
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("El nombre del kiosco es obligatorio.", "error")
        return redirect(url_for("panel.detalle_recinto", recinto_id=recinto_id))

    # Generar código de vinculación único (8 caracteres hex, legible)
    while True:
        codigo = secrets.token_hex(4).upper()
        if not Kiosco.query.filter_by(codigo_vinculacion=codigo).first():
            break

    kiosco = Kiosco(
        recinto_id=recinto_id,
        nombre=nombre,
        codigo_vinculacion=codigo,
        activo=True,
    )
    db.session.add(kiosco)
    db.session.commit()
    registrar_evento(g.usuario["id"], "KIOSCO_CREADO", f"Kiosco {nombre} en recinto {recinto.codigo}", ip=request.remote_addr)
    flash(f"Kiosco '{nombre}' creado. Código de vinculación: {codigo}", "success")
    return redirect(url_for("panel.detalle_recinto", recinto_id=recinto_id))


@bp.route("/recintos/<int:recinto_id>/kioscos/<int:kiosco_id>/toggle", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def toggle_kiosco(recinto_id, kiosco_id):
    kiosco = Kiosco.query.get_or_404(kiosco_id)
    kiosco.activo = not kiosco.activo
    db.session.commit()
    estado = "activado" if kiosco.activo else "desactivado"
    flash(f"Kiosco '{kiosco.nombre}' {estado}.", "success")
    return redirect(url_for("panel.detalle_recinto", recinto_id=recinto_id))
