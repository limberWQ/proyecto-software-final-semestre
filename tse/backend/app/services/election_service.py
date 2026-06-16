from app.extensions import db
from app.models import Eleccion, Recinto, RecintoEleccion, Departamento, Candidato
from app.blockchain.crypto import generar_par_claves_eleccion
from app.blockchain.chain import Blockchain
from app.services.audit_service import registrar_evento


class ElectionError(Exception):
    pass


def crear_eleccion(
    codigo: str,
    titulo: str,
    descripcion: str,
    tipo: str,
    departamento_id: int,
    fecha_inicio,
    fecha_fin,
    usuario_id: int,
    ip: str | None = None,
) -> Eleccion:
    """
    Crea una elección para UN departamento (cada departamento maneja su
    propia elección presidencial, para control independiente).
    Genera el par de claves RSA (pública/privada) y crea el bloque génesis
    de su blockchain.
    """
    if Eleccion.query.filter_by(codigo=codigo).first():
        raise ElectionError("Ya existe una elección con ese código")

    departamento = Departamento.query.get(departamento_id)
    if not departamento:
        raise ElectionError("Departamento inválido")

    clave_publica, clave_privada = generar_par_claves_eleccion()

    eleccion = Eleccion(
        codigo=codigo,
        titulo=titulo,
        descripcion=descripcion,
        tipo=tipo,
        estado="CONFIGURACION",
        departamento_id=departamento_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        clave_publica_pem=clave_publica,
        clave_privada_pem=clave_privada,
        created_by=usuario_id,
    )
    db.session.add(eleccion)
    db.session.commit()

    # Inicializa la blockchain (crea bloque génesis en disco)
    Blockchain.get_instance(eleccion.id)

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion.id,
        accion="ELECCION_CREADA",
        descripcion=f"Elección '{titulo}' creada para {departamento.nombre}",
        ip=ip,
    )
    return eleccion


def actualizar_eleccion(eleccion_id: int, datos: dict, usuario_id: int, ip: str | None = None) -> Eleccion:
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ElectionError("Elección no encontrada")

    if eleccion.estado != "CONFIGURACION":
        campos_permitidos = {"estado"}
        if set(datos.keys()) - campos_permitidos:
            raise ElectionError(
                "Solo se pueden editar los datos de la elección mientras está en CONFIGURACION"
            )

    for campo in ("titulo", "descripcion", "tipo", "fecha_inicio", "fecha_fin"):
        if campo in datos:
            setattr(eleccion, campo, datos[campo])

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion.id,
        accion="ELECCION_ACTUALIZADA",
        descripcion=f"Elección '{eleccion.titulo}' actualizada",
        ip=ip,
    )
    return eleccion


def cambiar_estado(eleccion_id: int, nuevo_estado: str, usuario_id: int, ip: str | None = None) -> Eleccion:
    """
    Transiciones válidas:
      CONFIGURACION -> ACTIVA
      ACTIVA -> SUSPENDIDA / CERRADA
      SUSPENDIDA -> ACTIVA / CERRADA
    CERRADA es estado final.
    """
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ElectionError("Elección no encontrada")

    transiciones_validas = {
        "CONFIGURACION": {"ACTIVA"},
        "ACTIVA": {"SUSPENDIDA", "CERRADA"},
        "SUSPENDIDA": {"ACTIVA", "CERRADA"},
        "CERRADA": set(),
    }

    if nuevo_estado not in transiciones_validas.get(eleccion.estado, set()):
        raise ElectionError(f"Transición inválida: {eleccion.estado} -> {nuevo_estado}")

    if nuevo_estado == "ACTIVA" and eleccion.estado == "CONFIGURACION":
        if Candidato.query.filter_by(eleccion_id=eleccion.id, activo=True).count() == 0:
            raise ElectionError("No se puede activar una elección sin candidatos")

    eleccion.estado = nuevo_estado
    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion.id,
        accion="ELECCION_ESTADO_CAMBIADO",
        descripcion=f"Estado cambiado a {nuevo_estado}",
        ip=ip,
    )
    return eleccion


def asignar_recintos(eleccion_id: int, recinto_ids: list[int], usuario_id: int, ip: str | None = None):
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ElectionError("Elección no encontrada")

    # limpiar asignaciones previas
    RecintoEleccion.query.filter_by(eleccion_id=eleccion_id).delete()

    for recinto_id in recinto_ids:
        recinto = Recinto.query.get(recinto_id)
        if not recinto:
            continue
        if recinto.departamento_id != eleccion.departamento_id:
            raise ElectionError(
                f"El recinto {recinto.codigo} no pertenece al departamento de la elección"
            )
        db.session.add(RecintoEleccion(recinto_id=recinto_id, eleccion_id=eleccion_id))

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion.id,
        accion="RECINTOS_ASIGNADOS",
        descripcion=f"{len(recinto_ids)} recintos asignados a la elección",
        ip=ip,
    )
    return eleccion


def listar_elecciones(departamento_id: int | None = None):
    query = Eleccion.query
    if departamento_id:
        query = query.filter_by(departamento_id=departamento_id)
    return query.order_by(Eleccion.created_at.desc()).all()


def obtener_eleccion(eleccion_id: int) -> Eleccion:
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise ElectionError("Elección no encontrada")
    return eleccion


def recintos_de_eleccion(eleccion_id: int) -> list[Recinto]:
    return (
        Recinto.query.join(RecintoEleccion, RecintoEleccion.recinto_id == Recinto.id)
        .filter(RecintoEleccion.eleccion_id == eleccion_id)
        .all()
    )

def obtener_eleccion_activa_por_recinto(recinto_id: int) -> Eleccion | None:
    """
    Busca una elección que esté en estado 'ACTIVA' y que tenga
    asignado el recinto dado a través de la tabla intermedia RecintoEleccion.
    """
    return (
        Eleccion.query
        .join(RecintoEleccion, RecintoEleccion.eleccion_id == Eleccion.id)
        .filter(RecintoEleccion.recinto_id == recinto_id)
        .filter(Eleccion.estado == "ACTIVA")
        .first()
    )