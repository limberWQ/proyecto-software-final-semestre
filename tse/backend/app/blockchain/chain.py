import json
import os
import threading
from datetime import datetime

from app.blockchain.block import Block

_BASE_DIR = os.path.join(
    os.path.dirname(__file__),  # app/blockchain/
    '..', '..', 'blockchain_data'
)


class Blockchain:
    """
    Gestiona la cadena de bloques de una elección específica.

    - Patrón singleton: una sola instancia por eleccion_id
    - Persistencia: lee y escribe blockchain_data/eleccion_{id:03d}/chain.json
    - Thread-safe: usa threading.Lock para escrituras concurrentes
    """

    _instancia: dict = {}
    _lock_global = threading.Lock()

    @classmethod
    def get_instance(cls, eleccion_id: int) -> 'Blockchain':
        with cls._lock_global:
            if eleccion_id not in cls._instancia:
                cls._instancia[eleccion_id] = cls(eleccion_id)
            return cls._instancia[eleccion_id]

    @classmethod
    def limpiar_instancia(cls, eleccion_id: int):
        with cls._lock_global:
            cls._instancia.pop(eleccion_id, None)

    def __init__(self, eleccion_id: int):
        self.eleccion_id = eleccion_id
        self._write_lock = threading.Lock()
        self.filepath = self._build_filepath(eleccion_id)
        self.chain: list[Block] = self._cargar_o_crear()

    def _build_filepath(self, eleccion_id: int) -> str:
        directorio = os.path.join(_BASE_DIR, f'eleccion_{eleccion_id:03d}')
        os.makedirs(directorio, exist_ok=True)
        return os.path.join(directorio, 'chain.json')

    def _cargar_o_crear(self) -> list:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                chain = [Block.from_dict(b) for b in data]
                print(
                    f"[Blockchain] Elección {self.eleccion_id}: "
                    f"{len(chain)} bloques cargados desde disco"
                )
                return chain
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[Blockchain] Error al cargar chain.json: {e}")
                raise RuntimeError(
                    f"chain.json de elección {self.eleccion_id} está corrupto: {e}"
                )
        else:
            genesis = self._crear_genesis()
            self._escribir([genesis])
            print(f"[Blockchain] Elección {self.eleccion_id}: bloque génesis creado")
            return [genesis]

    def _crear_genesis(self) -> Block:
        return Block(index=0, transactions=[], previous_hash='0' * 64, nonce=0)

    @property
    def ultimo_bloque(self) -> Block:
        return self.chain[-1]

    @property
    def longitud(self) -> int:
        return len(self.chain)

    def add_votes(self, transaccion: dict) -> Block:
        """
        Crea un nuevo bloque con la transacción del voto y lo agrega a la
        cadena. Escribe inmediatamente a disco. Thread-safe.
        """
        with self._write_lock:
            nuevo = Block(
                index=len(self.chain),
                transactions=[transaccion],
                previous_hash=self.ultimo_bloque.hash,
            )
            self.chain.append(nuevo)
            self._escribir(self.chain)
            return nuevo

    def _escribir(self, chain: list):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(
                [b.to_dict() for b in chain],
                f,
                indent=2,
                ensure_ascii=False,
            )

    def is_valid(self) -> bool:
        """
        Verifica la integridad completa de la cadena:
          1. el hash almacenado coincide con el recalculado
          2. el previous_hash coincide con el hash del bloque anterior
        """
        for i in range(1, len(self.chain)):
            bloque_actual = self.chain[i]
            bloque_anterior = self.chain[i - 1]

            if bloque_actual.hash != bloque_actual.recalculate_hash():
                print(f"[Blockchain] Bloque {i} comprometido: hash no coincide")
                return False

            if bloque_actual.previous_hash != bloque_anterior.hash:
                print(
                    f"[Blockchain] Bloque {i} desconectado: previous_hash "
                    f"no coincide con hash del bloque {i - 1}"
                )
                return False
        return True

    def get_all_blocks(self) -> list:
        return [b.to_dict() for b in self.chain]

    def find_block_by_hash(self, block_hash: str) -> dict | None:
        for bloque in self.chain:
            if bloque.hash == block_hash:
                return bloque.to_dict()
        return None

    def find_block_by_receipt(self, codigo_recibo: str) -> dict | None:
        for bloque in self.chain:
            for tx in bloque.transactions:
                if tx.get('receipt') == codigo_recibo:
                    return bloque.to_dict()
        return None

    def get_transactions(self) -> list:
        txs = []
        for bloque in self.chain[1:]:
            txs.extend(bloque.transactions)
        return txs

    def reemplazar_cadena(self, nueva_cadena: list) -> bool:
        """
        Reemplaza la cadena local si la nueva es más larga y válida.
        Regla de consenso: la cadena más larga válida gana.
        """
        if len(nueva_cadena) <= len(self.chain):
            return False

        bloques = [Block.from_dict(b) for b in nueva_cadena]

        cadena_temp = Blockchain.__new__(Blockchain)
        cadena_temp.chain = bloques
        cadena_temp.eleccion_id = self.eleccion_id

        if not cadena_temp.is_valid():
            print("[Blockchain] Cadena recibida inválida. Se rechaza")
            return False

        with self._write_lock:
            self.chain = bloques
            self._escribir(self.chain)
            print(f"[Blockchain] Cadena reemplazada. Nueva longitud: {len(self.chain)} bloques")
            return True

    def __repr__(self) -> str:
        return (
            f"Blockchain(eleccion={self.eleccion_id}, "
            f"bloques={len(self.chain)}, "
            f"valida={self.is_valid()})"
        )
