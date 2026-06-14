import hashlib
import json
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from ecdsa import SECP256k1, SigningKey, VerifyingKey, BadSignatureError


# ──────────────────────────────────────────────────────────────
#  Par de claves RSA por elección
# ──────────────────────────────────────────────────────────────

def generar_par_claves_eleccion() -> tuple[str, str]:
    """
    Genera un par de claves RSA 2048 bits para una elección.
    Se llama una sola vez al crear la elección en election_service.py.

    Retorna: (clave_publica_pem, clave_privada_pem) como strings PEM.
    - La clave pública se usa para cifrar cada voto al emitirlo.
    - La clave privada se usa para descifrar al cerrar la elección y
      calcular el conteo final. Se guarda en elecciones.clave_privada_pem.
    """
    clave_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    privada_pem = clave_privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    publica_pem = clave_privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')

    return publica_pem, privada_pem


def cargar_clave_publica(pem: str) -> RSAPublicKey:
    return serialization.load_pem_public_key(pem.encode('utf-8'))


def cargar_clave_privada(pem: str) -> RSAPrivateKey:
    return serialization.load_pem_private_key(pem.encode('utf-8'), password=None)


# ──────────────────────────────────────────────────────────────
#  Cifrado y descifrado de votos (RSA-OAEP)
# ──────────────────────────────────────────────────────────────

class VoteCipher:
    """
    Cifrado de votos con RSA-OAEP + SHA-256.
    OAEP agrega aleatoriedad al cifrado, por lo que dos votos idénticos
    al mismo candidato producen cifrados distintos, impidiendo ataques
    de correlación.
    """

    def encrypt(self, candidato_id: int, clave_publica: RSAPublicKey) -> str:
        voto_bytes = str(candidato_id).encode('utf-8')

        cifrado = clave_publica.encrypt(
            voto_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return cifrado.hex()

    def decrypt(self, encrypted_hex: str, clave_privada: RSAPrivateKey) -> int:
        cifrado_bytes = bytes.fromhex(encrypted_hex)

        descifrado = clave_privada.decrypt(
            cifrado_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return int(descifrado.decode('utf-8'))

    def encrypt_blanco_nulo(self, tipo: str, clave_publica: RSAPublicKey) -> str:
        """Cifra el voto blanco o nulo. BLANCO=0, NULO=-1."""
        codigos = {'BLANCO': 0, 'NULO': -1}
        return self.encrypt(codigos.get(tipo, 0), clave_publica)


# ──────────────────────────────────────────────────────────────
#  Firma digital ECDSA por transacción
# ──────────────────────────────────────────────────────────────

class TransactionSigner:
    """
    Firma cada transacción de voto con ECDSA sobre la curva secp256k1
    (igual que Bitcoin). La firma garantiza que la transacción no fue
    alterada después de ser emitida; no identifica al votante.
    """

    @staticmethod
    def generar_clave_sesion() -> tuple[str, str]:
        """
        Genera un par de claves ECDSA efímero para firmar una
        transacción. Retorna (clave_privada_hex, clave_publica_hex).
        """
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.get_verifying_key()
        return sk.to_string().hex(), vk.to_string().hex()

    @staticmethod
    def firmar(transaction: dict, clave_privada_hex: str) -> str:
        """Firma el hash SHA-256 de la transacción. Retorna firma en hexadecimal."""
        sk = SigningKey.from_string(bytes.fromhex(clave_privada_hex), curve=SECP256k1)

        tx_bytes = json.dumps(transaction, sort_keys=True, ensure_ascii=False).encode('utf-8')
        tx_hash = hashlib.sha256(tx_bytes).digest()

        firma = sk.sign(tx_hash)
        return firma.hex()

    @staticmethod
    def verificar(transaction: dict, firma_hex: str, clave_publica_hex: str) -> bool:
        """
        Verifica que la firma de una transacción es válida.
        Usado por node_sync.py al recibir bloques de otros nodos.
        """
        try:
            vk = VerifyingKey.from_string(bytes.fromhex(clave_publica_hex), curve=SECP256k1)

            tx_sin_firma = {
                k: v for k, v in transaction.items()
                if k not in ('signature', 'signer_pubkey')
            }
            tx_bytes = json.dumps(tx_sin_firma, sort_keys=True, ensure_ascii=False).encode('utf-8')
            tx_hash = hashlib.sha256(tx_bytes).digest()

            vk.verify(bytes.fromhex(firma_hex), tx_hash)
            return True

        except BadSignatureError:
            return False


# ──────────────────────────────────────────────────────────────
#  Token anónimo del votante / recibo
# ──────────────────────────────────────────────────────────────

def generar_voter_token(padron_id: int) -> str:
    salt = secrets.token_hex(16)
    combinacion = f"{padron_id}:{salt}"
    return hashlib.sha256(combinacion.encode('utf-8')).hexdigest()


def generar_codigo_recibo() -> str:
    return secrets.token_hex(16)


# ──────────────────────────────────────────────────────────────
#  Verificación biométrica
# ──────────────────────────────────────────────────────────────

def generar_hash_biometrico(dato_biometrico: bytes) -> str:
    return hashlib.sha256(dato_biometrico).hexdigest()
