from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, g
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies, verify_jwt_in_request, get_jwt

from app.services import auth_service

bp = Blueprint("auth_web", __name__, url_prefix="/")


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Si ya tiene sesión válida, redirigir según rol
    try:
        verify_jwt_in_request(locations=["cookies"])
        claims = get_jwt()
        rol_id = claims.get("rol_id")
        if rol_id == 2:
            return redirect(url_for("operador.verificar"))
        else:
            return redirect(url_for("panel.inicio"))
    except Exception:
        pass  # No hay sesión, mostrar login normal

    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Ingresa tu correo y contraseña.", "error")
        return redirect(url_for("auth_web.login"))

    try:
        usuario = auth_service.autenticar(email, password, ip=request.remote_addr)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return redirect(url_for("auth_web.login"))

    token = create_access_token(
        identity=str(usuario.id),
        additional_claims={
            "rol_id": usuario.rol_id,
            "rol_nombre": usuario.rol.nombre,
            "nombre_completo": usuario.nombre_completo,
            "recinto_id": usuario.recinto_id,
        },
    )

    if usuario.rol_id == usuario.ROL_OPERADOR:
        destino = url_for("operador.verificar")
    else:
        destino = url_for("panel.inicio")

    resp = make_response(redirect(destino))
    set_access_cookies(resp, token)
    return resp


@bp.route("/logout")
def logout():
    resp = make_response(redirect(url_for("auth_web.login")))
    unset_jwt_cookies(resp)
    flash("Sesión cerrada correctamente.", "success")
    return resp


@bp.route("/")
def raiz():
    return redirect(url_for("auth_web.login"))