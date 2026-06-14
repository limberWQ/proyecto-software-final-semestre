import hashlib
from datetime import datetime

from app.extensions import db
from app.models import (
    PadronElectoral,
    SesionKiosco,
    Kiosco,
    Eleccion,
    Conteo,
    Recibo,
)
from app.blockchain.chain import Blockchain
from app.blockchain.crypto import (
    VoteCipher,
    TransactionSigner,
    generar_voter_token,
    generar_codigo_recibo,
    cargar_clave_publica,
)
from app.blockchain import node_sync
from app.services.audit_service import registrar_evento


class VoteError(Exception):
    pass


# ──────────────────────────────────────────────────────────────
#  Vinculación de kiosco (celular) mediante código fijo
# ──────────────────────────────────────────────────────────────

def vincular_kiosco(codigo_vinculacion: str) -> dict:
    """
    El celular ingresa el código fijo que le indica el operador (PC3).
    Si es válido, devuelve los datos del kiosco para que el celular
    lo guarde localmente (localStorage) y lo use en cada consulta de estado.

    La vinculación permanece vigente hasta que la elección asociada
    termine (estado CERRADA); no expira por inactividad.
    """
    kiosco = Kiosco.query.filter_by(codigo_vinculacion=codigo_vinculacion, activo=True).first()
    if not kiosco:
        raise VoteError("Código de kiosco inválido")

    return {
        "kiosco_id": kiosco.id,
        "nombre": kiosco.nombre,
        "recinto_id": kiosco.recinto_id,
        "recinto_nombre": kiosco.recinto.nombre,
    }


# ──────────────────────────────────────────────────────────────
#  Habilitación de mesa/kiosco por el operador (PC3)
# ──────────────────────────────────────────────────────────────

def habilitar_kiosco(
    eleccion_id: int,
    ci: str,
    kiosco_id: int,
    operador_id: int,
    ip: str | None = None,
) -> SesionKiosco:
    """
    El operador verifica al votante por CI y habilita el kiosco vinculado
    por 5 minutos. Validaciones:
      - el votante debe existir en el padrón de esta elección
      - debe estar habilitado (habilitado=True)
      - no debe haber votado ya (ya_voto=False)
      - el kiosco debe pertenecer al recinto del operador
      - no debe existir ya una sesión vigente para ese kiosco
    """
    votante = PadronElectoral.query.filter_by(eleccion_id=eleccion_id, ci=ci).first()
    if not votante:
        raise VoteError("El ciudadano no se encuentra en el padrón de esta elección")

    if not votante.habilitado:
        raise VoteError(f"Votante inhabilitado: {votante.motivo_inhabilitacion or 'sin motivo registrado'}")

    if votante.ya_voto:
        raise VoteError("Este ciudadano ya emitió su voto en esta elección")

    kiosco = Kiosco.query.get(kiosco_id)
    if not kiosco or not kiosco.activo:
        raise VoteError("Kiosco no válido")

    # Verificar que no haya una sesión vigente en este kiosco
    sesion_vigente = (
        SesionKiosco.query.filter_by(kiosco_id=kiosco_id)
        .filter(SesionKiosco.estado.in_(("PENDIENTE", "ACTIVA")))
        .filter(SesionKiosco.expira_en > datetime.utcnow())
        .first()
    )
    if sesion_vigente:
        raise VoteError("El kiosco ya tiene una sesión de votación activa")

    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion or not eleccion.esta_activa:
        raise VoteError("La elección no está activa")

    token_raw = f"{votante.id}:{kiosco_id}:{datetime.utcnow().timestamp()}"
    token_hash = hashlib.sha256(token_raw.encode("utf-8")).hexdigest()

    sesion = SesionKiosco(
        operador_id=operador_id,
        padron_id=votante.id,
        kiosco_id=kiosco_id,
        token_hash=token_hash,
        estado="PENDIENTE",
        expira_en=SesionKiosco.calcular_expiracion(),
    )
    db.session.add(sesion)

    kiosco.ultimo_uso = datetime.utcnow()
    db.session.commit()

    registrar_evento(
        usuario_id=operador_id,
        eleccion_id=eleccion_id,
        accion="KIOSCO_HABILITADO",
        descripcion=f"Kiosco {kiosco.nombre} habilitado para votante CI={ci} (5 min)",
        ip=ip,
    )
    return sesion


def estado_kiosco(kiosco_id: int) -> dict:
    """
    Consultado periódicamente por el celular (polling) para saber si
    debe mostrar la papeleta o el mensaje "kiosco no habilitado".

    Retorna:
      {
        "habilitado": bool,
        "segundos_restantes": int,
        "eleccion_id": int | None,
        "sesion_id": int | None,
        "ya_completada": bool
      }
    """
    sesion = (
        SesionKiosco.query.filter_by(kiosco_id=kiosco_id)
        .filter(SesionKiosco.estado.in_(("PENDIENTE", "ACTIVA")))
        .order_by(SesionKiosco.created_at.desc())
        .first()
    )

    if not sesion:
        return {"habilitado": False, "segundos_restantes": 0, "eleccion_id": None, "sesion_id": None}

    if not sesion.esta_vigente:
        # marcar como expirada
        sesion.estado = "EXPIRADA"
        db.session.commit()
        return {"habilitado": False, "segundos_restantes": 0, "eleccion_id": None, "sesion_id": None}

    # marcar como ACTIVA en el primer "ping" del celular
    if sesion.estado == "PENDIENTE":
        sesion.estado = "ACTIVA"
        db.session.commit()

    return {
        "habilitado": True,
        "segundos_restantes": sesion.segundos_restantes,
        "eleccion_id": sesion.padron.eleccion_id,
        "sesion_id": sesion.id,
    }


# ──────────────────────────────────────────────────────────────
#  Emisión del voto
# ──────────────────────────────────────────────────────────────

def emitir_voto(sesion_id: int, candidato_id: int | None, tipo_voto: str, ip: str | None = None) -> dict:
    """
    Procesa la emisión de un voto desde el kiosco (celular).

    Args:
        sesion_id: id de la SesionKiosco vigente (ACTIVA)
        candidato_id: id del candidato elegido, o None si tipo_voto != 'VALIDO'
        tipo_voto: 'VALIDO' | 'BLANCO' | 'NULO'

    Flujo:
      1. Valida que la sesión esté vigente y no completada
      2. Cifra el voto con la clave pública RSA de la elección
      3. Genera token anónimo del votante (no expone el padron_id real)
      4. Firma la transacción con ECDSA (clave efímera de sesión)
      5. Agrega el bloque a la blockchain (persistido en chain.json)
      6. Propaga el bloque a los otros nodos (best-effort)
      7. Genera recibo con el hash del bloque
      8. Marca al votante como ya_voto=True
      9. Marca la sesión como COMPLETADA y el kiosco queda libre
         automáticamente (sin esperar el resto del temporizador)
      10. Incrementa el contador de participación en tiempo real

    Retorna:
      { "codigo_recibo": str, "block_hash": str, "block_index": int }
    """
    if tipo_voto not in ("VALIDO", "BLANCO", "NULO"):
        raise VoteError("Tipo de voto inválido")

    if tipo_voto == "VALIDO" and not candidato_id:
        raise VoteError("Debe especificar un candidato para voto VALIDO")

    sesion = SesionKiosco.query.get(sesion_id)
    if not sesion:
        raise VoteError("Sesión de votación no encontrada")

    if sesion.estado == "COMPLETADA":
        raise VoteError("Esta sesión ya emitió su voto")

    if not sesion.esta_vigente:
        sesion.estado = "EXPIRADA"
        db.session.commit()
        raise VoteError("La sesión de votación expiró")

    votante = sesion.padron
    if votante.ya_voto:
        raise VoteError("Este ciudadano ya emitió su voto")

    eleccion = Eleccion.query.get(votante.eleccion_id)
    if not eleccion or not eleccion.esta_activa:
        raise VoteError("La elección no está activa")

    if tipo_voto == "VALIDO":
        from app.models import Candidato
        candidato = Candidato.query.filter_by(
            id=candidato_id, eleccion_id=eleccion.id, activo=True
        ).first()
        if not candidato:
            raise VoteError("Candidato inválido para esta elección")

    # 1. Cifrar voto
    clave_publica = cargar_clave_publica(eleccion.clave_publica_pem)
    cipher = VoteCipher()
    if tipo_voto == "VALIDO":
        encrypted_vote = cipher.encrypt(candidato_id, clave_publica)
    else:
        encrypted_vote = cipher.encrypt_blanco_nulo(tipo_voto, clave_publica)

    # 2. Token anónimo y recibo
    voter_token = generar_voter_token(votante.id)
    codigo_recibo = generar_codigo_recibo()

    transaccion = {
        "voter_token": voter_token,
        "encrypted_vote": encrypted_vote,
        "election_id": eleccion.id,
        "receipt": codigo_recibo,
    }

    # 3. Firmar transacción (clave efímera generada por transacción,
    # ya que no se persiste una clave de sesión por kiosco)
    clave_priv_hex, clave_pub_hex = TransactionSigner.generar_clave_sesion()
    firma = TransactionSigner.firmar(transaccion, clave_priv_hex)
    transaccion["signature"] = firma
    transaccion["signer_pubkey"] = clave_pub_hex

    # 4. Agregar a la blockchain
    blockchain = Blockchain.get_instance(eleccion.id)
    bloque = blockchain.add_votes(transaccion)

    # 5. Propagar a otros nodos (best-effort, no bloquea el voto)
    try:
        node_sync.programar(bloque)
    except Exception:
        pass

    # 6. Generar recibo en BD
    recibo = Recibo(
        padron_id=votante.id,
        eleccion_id=eleccion.id,
        codigo_recibo=codigo_recibo,
        block_hash=bloque.hash,
        impreso=False,
    )
    db.session.add(recibo)

    # 7. Marcar votante y sesión
    votante.ya_voto = True
    votante.hora_voto = datetime.utcnow()
    sesion.estado = "COMPLETADA"

    # 8. Actualizar conteo de participación en tiempo real (no por candidato,
    # ya que el voto está cifrado hasta el cierre de la elección)
    _incrementar_participacion(eleccion.id)

    db.session.commit()

    registrar_evento(
        usuario_id=None,
        eleccion_id=eleccion.id,
        accion="VOTO_EMITIDO",
        descripcion=f"Voto registrado en bloque #{bloque.index} (recibo {codigo_recibo})",
        ip=ip,
    )

    return {
        "codigo_recibo": codigo_recibo,
        "block_hash": bloque.hash,
        "block_index": bloque.index,
    }


def _incrementar_participacion(eleccion_id: int):
    """
    Mantiene un registro agregado de "votos emitidos" (participación)
    en la tabla conteos, usando candidato_id=NULL y tipo='VALIDO' como
    fila especial de participación total. Esto permite mostrar en el
    dashboard en tiempo real cuántas personas han votado sin revelar
    por quién (eso requiere descifrado al cierre).
    """
    fila = Conteo.query.filter_by(eleccion_id=eleccion_id, candidato_id=None, tipo="VALIDO").first()
    if not fila:
        fila = Conteo(eleccion_id=eleccion_id, candidato_id=None, tipo="VALIDO", total_votos=0)
        db.session.add(fila)
    fila.total_votos += 1


def participacion_eleccion(eleccion_id: int) -> dict:
    """Devuelve el total de votos emitidos y el padrón total para calcular % de participación."""
    fila = Conteo.query.filter_by(eleccion_id=eleccion_id, candidato_id=None, tipo="VALIDO").first()
    total_votos = fila.total_votos if fila else 0
    total_padron = PadronElectoral.query.filter_by(eleccion_id=eleccion_id).count()
    porcentaje = round((total_votos / total_padron) * 100, 2) if total_padron > 0 else 0.0
    return {
        "total_votos": total_votos,
        "total_padron": total_padron,
        "porcentaje_participacion": porcentaje,
    }
