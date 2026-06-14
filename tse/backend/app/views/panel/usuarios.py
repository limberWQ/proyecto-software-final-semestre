from flask import render_template, request, redirect, url_for, flash, g

from app.models import Usuario, Rol, Recinto
from app.services import auth_service
from app.views.web_decorators import rol_web_requerido
from app.views.panel import bp


@bp.route("/usuarios")
@rol_web_requerido(Usuario.ROL_ADMIN)
def usuarios():
    rol_filtro = request.args.get("rol_id", type=int)
    lista = auth_service.listar_usuarios(rol_id=rol_filtro)
    roles = Rol.query.all()
    return render_template(
        "admin/users/users.html",
        usuario=g.usuario,
        active="usuarios",
        usuarios=lista,
        roles=roles,
        rol_filtro=rol_filtro,
    )


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def nuevo_usuario():
    roles = Rol.query.all()
    recintos = Recinto.query.filter_by(activo=True).order_by(Recinto.nombre).all()

    if request.method == "GET":
        return render_template(
            "admin/users/create_user.html",
            usuario=g.usuario,
            active="usuarios",
            roles=roles,
            recintos=recintos,
        )

    data = request.form
    try:
        auth_service.crear_usuario(
            ci=data["ci"].strip(),
            nombres=data["nombres"].strip(),
            apellidos=data["apellidos"].strip(),
            email=data["email"].strip(),
            password=data["password"],
            rol_id=int(data["rol_id"]),
            recinto_id=data.get("recinto_id", type=int),
            creado_por=g.usuario["id"],
            ip=request.remote_addr,
        )
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.nuevo_usuario"))

    flash("Usuario creado correctamente.", "success")
    return redirect(url_for("panel.usuarios"))


@bp.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def editar_usuario(uid):
    u = Usuario.query.get(uid)
    if not u:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("panel.usuarios"))

    roles = Rol.query.all()
    recintos = Recinto.query.filter_by(activo=True).order_by(Recinto.nombre).all()

    if request.method == "GET":
        return render_template(
            "admin/users/edit_user.html",
            usuario=g.usuario,
            active="usuarios",
            u=u,
            roles=roles,
            recintos=recintos,
        )

    data = request.form
    u.nombres = data.get("nombres", u.nombres).strip()
    u.apellidos = data.get("apellidos", u.apellidos).strip()
    u.email = data.get("email", u.email).strip()

    nuevo_rol = data.get("rol_id", type=int)
    if nuevo_rol:
        u.rol_id = nuevo_rol

    nuevo_recinto = data.get("recinto_id", type=int)
    u.recinto_id = nuevo_recinto if u.rol_id == Usuario.ROL_OPERADOR else None

    from app.extensions import db
    db.session.commit()
    flash("Usuario actualizado.", "success")
    return redirect(url_for("panel.usuarios"))


@bp.route("/usuarios/<int:uid>/cambiar-password", methods=["GET", "POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def cambiar_password(uid):
    u = Usuario.query.get(uid)
    if not u:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("panel.usuarios"))

    if request.method == "GET":
        return render_template(
            "admin/users/change_password.html",
            usuario=g.usuario,
            active="usuarios",
            u=u,
        )

    nueva = request.form.get("nueva_password", "")
    if len(nueva) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("panel.cambiar_password", uid=uid))

    try:
        auth_service.cambiar_password(
            usuario_id=uid, nueva_password=nueva, cambiado_por=g.usuario["id"], ip=request.remote_addr
        )
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return redirect(url_for("panel.cambiar_password", uid=uid))

    flash("Contraseña actualizada.", "success")
    return redirect(url_for("panel.usuarios"))


@bp.route("/usuarios/<int:uid>/eliminar", methods=["POST"])
@rol_web_requerido(Usuario.ROL_ADMIN)
def eliminar_usuario(uid):
    justificacion = request.form.get("justificacion", "").strip()
    try:
        auth_service.eliminar_usuario(
            usuario_id=uid,
            justificacion=justificacion,
            eliminado_por=g.usuario["id"],
            ip=request.remote_addr,
        )
    except auth_service.AuthError as e:
        flash(str(e), "error")
    else:
        flash("Usuario desactivado correctamente.", "success")

    return redirect(url_for("panel.usuarios"))
