import os
from flask import Flask
from app.config import Config
from app.extensions import db, jwt

# __file__ = /app/backend/app/__init__.py
# dirname x1 = /app/backend/app
# dirname x2 = /app/backend
# dirname x3 = /app  ← aquí está frontend/
_BASE      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TEMPLATES = os.path.abspath(os.path.join(_BASE, 'frontend', 'templates'))
_STATIC    = os.path.abspath(os.path.join(_BASE, 'frontend', 'static'))


def create_app():
    app = Flask(__name__, template_folder=_TEMPLATES, static_folder=_STATIC)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    from app import models  # noqa: F401

    from app.routes import auth, elections, candidates, padron, kiosk, votes, results, audit

    app.register_blueprint(auth.bp)
    app.register_blueprint(elections.bp)
    app.register_blueprint(candidates.bp)
    app.register_blueprint(padron.bp)
    app.register_blueprint(kiosk.bp)
    app.register_blueprint(votes.bp)
    app.register_blueprint(results.bp)
    app.register_blueprint(results.bp_pub)
    app.register_blueprint(audit.bp)

    from app.views.auth_web import bp as auth_web_bp
    from app.views.panel import bp as panel_bp
    from app.views.operador import bp as operador_bp

    app.register_blueprint(auth_web_bp)
    app.register_blueprint(panel_bp)
    app.register_blueprint(operador_bp)

    @app.route("/votacion")
    def kiosco_ballot():
        from flask import render_template as _rt
        return _rt("voter/ballot.html")

    @app.route("/blockchain/health", methods=["GET"])
    def health():
        from app.blockchain import node_sync
        return {"activo": True, "nodo": node_sync.NODO_ACTUAL}

    @app.route("/blockchain/cadena/<int:eleccion_id>", methods=["GET"])
    def cadena_publica(eleccion_id):
        from app.blockchain import node_sync
        return node_sync.obtener_cadena(eleccion_id)

    @app.route("/blockchain/recibir_bloque", methods=["POST"])
    def recibir_bloque():
        from flask import request, jsonify
        from app.blockchain import node_sync

        data = request.get_json(silent=True) or {}
        eleccion_id = data.get("eleccion_id")
        block_data = data.get("block")

        if not eleccion_id or not block_data:
            return jsonify({"error": "eleccion_id y block son requeridos"}), 400

        ok, motivo = node_sync.recibir_bloque(eleccion_id, block_data)
        if not ok:
            return jsonify({"aceptado": False, "motivo": motivo}), 409

        return jsonify({"aceptado": True})

    @app.route("/api/health", methods=["GET"])
    def api_health():
        return {"status": "ok", "servicio": "TSE Backend"}

    return app