import hashlib
from functools import wraps

from flask import request, jsonify
from models import ApiKey

# Para obtener ciudadanos, en el header poner:
# Authorization: Bearer TSE-SECRET-KEY-2025


def require_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "API key requerida"}), 401

        try:
            scheme, raw_key = auth_header.split()
        except ValueError:
            return jsonify({"error": "Formato inválido"}), 401

        if scheme.lower() != "bearer":
            return jsonify({"error": "Usa Bearer token"}), 401

        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        key = ApiKey.query.filter_by(
            api_key_hash=hashed_key,
            activo=True
        ).first()

        if not key:
            return jsonify({"error": "API key inválida"}), 403

        return func(*args, **kwargs)

    return wrapper
