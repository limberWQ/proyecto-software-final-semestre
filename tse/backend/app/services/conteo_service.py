from app.extensions import db
from app.models import Eleccion, Candidato, Conteo
from app.blockchain.chain import Blockchain
from app.blockchain.crypto import VoteCipher, cargar_clave_privada
from app.services.audit_service import registrar_evento
from app.services.vote_service import participacion_eleccion


class ConteoError(Exception):
    pass


def cerrar_y_contar(eleccion_id: int, usuario_id: int, ip: str | None = None) -> dict:
    """
    Cierra la elección (estado=CERRADA) y descifra todos los votos de la
    blockchain usando la clave privada RSA de la elección, generando el
    conteo final por candidato, blancos y nulos.

    Solo el ADMIN puede ejecutar esta acción.
    """
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ConteoError("Elección no encontrada")

    if eleccion.estado not in ("ACTIVA", "SUSPENDIDA", "CERRADA"):
        raise ConteoError("La elección debe estar activa o suspendida para cerrarse")

    if not eleccion.clave_privada_pem:
        raise ConteoError("La elección no tiene clave privada registrada")

    clave_privada = cargar_clave_privada(eleccion.clave_privada_pem)
    cipher = VoteCipher()

    blockchain = Blockchain.get_instance(eleccion_id)
    transacciones = blockchain.get_transactions()

    conteo_candidatos: dict[int, int] = {}
    conteo_blancos = 0
    conteo_nulos = 0
    errores_descifrado = 0

    for tx in transacciones:
        try:
            valor = cipher.decrypt(tx["encrypted_vote"], clave_privada)
        except Exception:
            errores_descifrado += 1
            continue

        if valor == 0:
            conteo_blancos += 1
        elif valor == -1:
            conteo_nulos += 1
        else:
            conteo_candidatos[valor] = conteo_candidatos.get(valor, 0) + 1

    # Persistir resultados: limpiar filas previas por candidato
    # (no se toca la fila de participación, candidato_id=NULL, tipo=VALIDO)
    Conteo.query.filter(
        Conteo.eleccion_id == eleccion_id, Conteo.candidato_id.isnot(None)
    ).delete()

    candidatos = Candidato.query.filter_by(eleccion_id=eleccion_id).all()
    for candidato in candidatos:
        total = conteo_candidatos.get(candidato.id, 0)
        db.session.add(
            Conteo(eleccion_id=eleccion_id, candidato_id=candidato.id, tipo="VALIDO", total_votos=total)
        )

    # BLANCO/NULO con candidato_id=NULL pero distinto tipo
    # (no chocan con la fila de participación, que usa tipo='VALIDO')
    db.session.add(
        Conteo(eleccion_id=eleccion_id, candidato_id=None, tipo="BLANCO", total_votos=conteo_blancos)
    )
    db.session.add(
        Conteo(eleccion_id=eleccion_id, candidato_id=None, tipo="NULO", total_votos=conteo_nulos)
    )

    if eleccion.estado != "CERRADA":
        eleccion.estado = "CERRADA"

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion="ELECCION_CERRADA_CONTADA",
        descripcion=(
            f"Elección cerrada y contada: {sum(conteo_candidatos.values())} votos válidos, "
            f"{conteo_blancos} blancos, {conteo_nulos} nulos, "
            f"{errores_descifrado} errores de descifrado"
        ),
        ip=ip,
    )

    return obtener_resultados(eleccion_id)


def obtener_resultados(eleccion_id: int) -> dict:
    """
    Resultados para el dashboard de resultados (results/dashboard.html).

    Mientras la elección está ACTIVA, solo se muestra la participación
    (votos emitidos vs padrón total), no el detalle por candidato, porque
    los votos siguen cifrados.

    Una vez CERRADA, se muestra el detalle completo por candidato.
    """
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ConteoError("Elección no encontrada")

    participacion = participacion_eleccion(eleccion_id)

    resultado = {
    "eleccion_id": eleccion.id,
    "titulo": eleccion.titulo,
    "estado": eleccion.estado,
    "participacion": participacion,
    "detalle_disponible": eleccion.estado == "CERRADA",
    "candidatos": [],
    "validos": None,   # <-- agregar
    "blancos": None,
    "nulos": None,
    }

    if eleccion.estado != "CERRADA":
        return resultado

    candidatos = Candidato.query.filter_by(eleccion_id=eleccion_id).order_by(Candidato.numero_lista).all()
    conteos = {
        (c.candidato_id, c.tipo): c.total_votos
        for c in Conteo.query.filter_by(eleccion_id=eleccion_id).all()
    }

    total_validos = sum(
        v for (cand_id, tipo), v in conteos.items() if tipo == "VALIDO" and cand_id is not None
    )

    for candidato in candidatos:
        votos = conteos.get((candidato.id, "VALIDO"), 0)
        porcentaje = round((votos / total_validos) * 100, 2) if total_validos > 0 else 0.0
        resultado["candidatos"].append(
            {
                "id": candidato.id,
                "numero_lista": candidato.numero_lista,
                "sigla_partido": candidato.sigla_partido,
                "nombre_completo": candidato.nombre_completo,
                "logo_partido": candidato.logo_partido,
                "color_partido": candidato.color_partido,
                "votos": votos,
                "porcentaje": porcentaje,
            }
        )

    resultado["candidatos"].sort(key=lambda c: c["votos"], reverse=True)
    resultado["validos"] = total_validos
    resultado["blancos"] = conteos.get((None, "BLANCO"), 0)
    resultado["nulos"] = conteos.get((None, "NULO"), 0)

    return resultado