import hashlib
import json
from datetime import datetime


class Block:
    """Representa un bloque de la cadena de bloques de una elección."""

    def __init__(self, index: int, transactions: list, previous_hash: str, nonce: int = 0):
        self.index = index
        self.timestamp = datetime.utcnow().isoformat()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.merkle_root = self._calculate_merkle_root()
        self.hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        block_data = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "merkle_root": self.merkle_root,
                "nonce": self.nonce,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(block_data.encode("utf-8")).hexdigest()

    def recalculate_hash(self) -> str:
        return self._calculate_hash()

    def _calculate_merkle_root(self) -> str:
        if not self.transactions:
            return hashlib.sha256(b"genesis").hexdigest()

        hashes = [
            hashlib.sha256(
                json.dumps(tx, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            for tx in self.transactions
        ]

        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])

            hashes = [
                hashlib.sha256((hashes[i] + hashes[i + 1]).encode("utf-8")).hexdigest()
                for i in range(0, len(hashes), 2)
            ]

        return hashes[0]

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        block = cls.__new__(cls)
        block.index = data["index"]
        block.timestamp = data["timestamp"]
        block.transactions = data["transactions"]
        block.previous_hash = data["previous_hash"]
        block.merkle_root = data["merkle_root"]
        block.nonce = data["nonce"]
        block.hash = data["hash"]
        return block

    def __repr__(self) -> str:
        return f"Block(index={self.index}, txs={len(self.transactions)}, hash={self.hash[:12]}...)"
