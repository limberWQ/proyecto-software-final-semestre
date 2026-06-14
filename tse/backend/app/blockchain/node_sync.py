import os
import requests

from app.blockchain.chain import Blockchain
from app.blockchain.block import Block

# Configuración de nodos: tres procesos Flask independientes.
# En docker-compose se definen como servicios separados.
# El nodo actual se identifica por la variable de entorno NODE_ID (1, 2, 3).

NODOS = {
    1: os.getenv('NODO_1_URL', 'http://tse_nodo1:5000'),
    2: os.getenv('NODO_2_URL', 'http://tse_nodo2:5000'),
    3: os.getenv('NODO_3_URL', 'http://tse_nodo3:5000'),
}

NODO_ACTUAL = int(os.getenv('NODE_ID', '1'))

TIMEOUT = 5


def _nodos_remotos() -> list[str]:
    """Devuelve las URLs de los nodos distintos al actual."""
    return [url for node_id, url in NODOS.items() if node_id != NODO_ACTUAL]


# ──────────────────────────────────────────────────────────────
#  Propagación de bloques nuevos
# ──────────────────────────────────────────────────────────────

def programar(block: Block) -> dict:
    """
    Envía un bloque nuevo a todos los nodos remotos.
    Se llama desde vote_service.py después de agregar el bloque a la
    cadena local. Best-effort: si un nodo falla, no bloquea el voto.

    Retorna: {"http://nodo2:5000": "ok" | "error..."}
    """
    resultados = {}
    block_data = block.to_dict()

    for url in _nodos_remotos():
        try:
            response = requests.post(
                f"{url}/blockchain/recibir_bloque",
                json={
                    'eleccion_id': block.transactions[0].get('election_id')
                    if block.transactions else 0,
                    'block': block_data,
                },
                timeout=TIMEOUT,
            )

            if response.status_code == 200:
                resultados[url] = 'ok'
            else:
                resultados[url] = f"error HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            resultados[url] = 'error: nodo no disponible'
        except requests.exceptions.Timeout:
            resultados[url] = 'error: timeout'
        except Exception as e:
            resultados[url] = f"error: {str(e)}"
    return resultados


# ──────────────────────────────────────────────────────────────
#  Recepción de bloques de otros nodos
# ──────────────────────────────────────────────────────────────

def recibir_bloque(eleccion_id: int, block_data: dict) -> tuple[bool, str]:
    """
    Procesa un bloque recibido de otro nodo. Validaciones:
      1. block_hash coincide con el hash recalculado (integridad)
      2. previous_hash coincide con el hash del último bloque local
      3. block_index es el siguiente esperado

    Retorna (True, "ok") si fue aceptado, (False, "motivo") si fue rechazado.
    """
    blockchain = Blockchain.get_instance(eleccion_id)
    bloque = Block.from_dict(block_data)

    if bloque.hash != bloque.recalculate_hash():
        return False, "hash del bloque inválido"

    ultimo = blockchain.ultimo_bloque

    if bloque.previous_hash != ultimo.hash:
        print(
            f"[NodeSync] Bloque {bloque.index} rechazado: "
            f"previous_hash no coincide, solicitando sincronización"
        )
        return False, "previous_hash no coincide -- se requiere sincronización"

    if bloque.index != ultimo.index + 1:
        return False, f"índice esperado {ultimo.index + 1}, recibido {bloque.index}"

    with blockchain._write_lock:
        blockchain.chain.append(bloque)
        blockchain._escribir(blockchain.chain)

    print(f"[NodeSync] Bloque {bloque.index} aceptado. Cadena local: {len(blockchain.chain)} bloques")
    return True, "ok"


# ──────────────────────────────────────────────────────────────
#  Sincronización entre nodos
# ──────────────────────────────────────────────────────────────

def sincronizar(eleccion_id: int) -> bool:
    """
    Solicita la cadena completa a todos los nodos remotos y reemplaza la
    cadena local si algún nodo tiene una cadena más larga y válida
    (regla de consenso: la cadena más larga válida gana).

    Retorna True si la cadena fue reemplazada, False si ya estaba actualizada.
    """
    blockchain = Blockchain.get_instance(eleccion_id)
    reemplazada = False

    for url in _nodos_remotos():
        try:
            response = requests.get(f"{url}/blockchain/cadena/{eleccion_id}", timeout=TIMEOUT)

            if response.status_code != 200:
                continue

            data = response.json()
            cadena_remota = data.get('chain', [])

            if blockchain.reemplazar_cadena(cadena_remota):
                print(
                    f"[NodeSync] Cadena de elección {eleccion_id} sincronizada "
                    f"desde {url}. Longitud: {len(cadena_remota)} bloques."
                )
                reemplazada = True

        except requests.exceptions.ConnectionError:
            print(f"[NodeSync] Nodo {url} no disponible para sincronización.")
        except requests.exceptions.Timeout:
            print(f"[NodeSync] Timeout al sincronizar con {url}.")
        except Exception as e:
            print(f"[NodeSync] Error sincronizando con {url}: {e}")

    return reemplazada


def obtener_cadena(eleccion_id: int) -> dict:
    """
    Devuelve la cadena completa de este nodo para compartirla con otros
    nodos. Se usa en GET /blockchain/cadena/<id>.
    """
    blockchain = Blockchain.get_instance(eleccion_id)
    return {
        'chain': blockchain.get_all_blocks(),
        'longitud': blockchain.longitud,
        'nodo': NODO_ACTUAL,
        'valida': blockchain.is_valid(),
    }


def estado_nodos() -> dict:
    """
    Consulta el estado de todos los nodos remotos. Usado en el panel
    de auditoría para mostrar cuántos nodos están activos y sincronizados.

    Returns:
        {
          1: {"activo": True, "nodo_actual": True},
          2: {"activo": True, "longitud": 45, "url": "..."},
          3: {"activo": False, "url": "..."}
        }
    """
    estado = {NODO_ACTUAL: {"activo": True, "nodo_actual": True}}

    for node_id, url in NODOS.items():
        if node_id == NODO_ACTUAL:
            continue
        try:
            response = requests.get(f"{url}/blockchain/health", timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                estado[node_id] = {
                    "activo": True,
                    "longitud": data.get('longitud'),
                    "url": url,
                }
            else:
                estado[node_id] = {"activo": False, "url": url}

        except Exception:
            estado[node_id] = {"activo": False, "url": url}

    return estado
