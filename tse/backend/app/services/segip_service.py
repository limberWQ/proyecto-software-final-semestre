import requests
from flask import current_app


class SegipError(Exception):
    pass


def _headers():
    api_key = current_app.config["SEGIP_API_KEY"]
    return {"Authorization": f"Bearer {api_key}"}


def obtener_todos_ciudadanos() -> list[dict]:
    """
    Llama a GET /ciudadanos del SEGIP y devuelve la lista completa de
    ciudadanos activos. Se usa al construir o actualizar el padrón TSE.

    Cada ciudadano viene con:
        ci, nombres, apellido_paterno, apellido_materno,
        departamento_id, fecha_nacimiento, sexo, vivo
    """
    base_url = current_app.config["SEGIP_API_URL"]
    try:
        resp = requests.get(f"{base_url}/ciudadanos", headers=_headers(), timeout=15)
    except requests.exceptions.ConnectionError:
        raise SegipError("No se pudo conectar con el servicio SEGIP")
    except requests.exceptions.Timeout:
        raise SegipError("Tiempo de espera agotado al consultar SEGIP")

    if resp.status_code in (401, 403):
        raise SegipError("API key inválida para el servicio SEGIP")
    if resp.status_code != 200:
        raise SegipError(f"SEGIP respondió con error HTTP {resp.status_code}")

    return resp.json()


def verificar_ciudadano(ci: str) -> dict | None:
    """
    Llama a GET /ciudadano/<ci> del SEGIP. Devuelve None si no existe.
    Se usa en la verificación que hace el operador antes de habilitar un kiosco.
    """
    base_url = current_app.config["SEGIP_API_URL"]
    try:
        resp = requests.get(f"{base_url}/ciudadano/{ci}", headers=_headers(), timeout=10)
    except requests.exceptions.ConnectionError:
        raise SegipError("No se pudo conectar con el servicio SEGIP")
    except requests.exceptions.Timeout:
        raise SegipError("Tiempo de espera agotado al consultar SEGIP")

    if resp.status_code == 404:
        return None
    if resp.status_code in (401, 403):
        raise SegipError("API key inválida para el servicio SEGIP")
    if resp.status_code != 200:
        raise SegipError(f"SEGIP respondió con error HTTP {resp.status_code}")

    data = resp.json()
    if not data.get("valido"):
        return None
    return data
