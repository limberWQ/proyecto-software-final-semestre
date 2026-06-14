from app.extensions import db
from app.models import Candidato, Eleccion
from app.services.audit_service import registrar_evento


class CandidatoError(Exception):
    pass


def crear_candidato(eleccion_id: int, datos: dict, usuario_id: int, ip: str | None = None) -> Candidato:
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise CandidatoError("Elección no encontrada")

    if eleccion.estado != "CONFIGURACION":
        raise CandidatoError("Solo se pueden agregar candidatos mientras la elección está en CONFIGURACION")

    existe = Candidato.query.filter_by(
        eleccion_id=eleccion_id, numero_lista=datos["numero_lista"]
    ).first()
    if existe:
        raise CandidatoError("Ya existe un candidato con ese número de lista en esta elección")

    candidato = Candidato(
        eleccion_id=eleccion_id,
        numero_lista=datos["numero_lista"],
        sigla_partido=datos["sigla_partido"],
        nombre_partido=datos.get("nombre_partido"),
        nombres=datos["nombres"],
        apellido_paterno=datos["apellido_paterno"],
        apellido_materno=datos.get("apellido_materno"),
        formula_nombres=datos.get("formula_nombres"),
        formula_apellido_paterno=datos.get("formula_apellido_paterno"),
        logo_partido=datos.get("logo_partido"),
        foto_candidato=datos.get("foto_candidato"),
        color_partido=datos.get("color_partido"),
        propuesta_breve=datos.get("propuesta_breve"),
        activo=True,
    )
    db.session.add(candidato)
    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion="CANDIDATO_CREADO",
        descripcion=f"Candidato #{candidato.numero_lista} ({candidato.sigla_partido}) - {candidato.nombre_completo}",
        ip=ip,
    )
    return candidato


def actualizar_candidato(candidato_id: int, datos: dict, usuario_id: int, ip: str | None = None) -> Candidato:
    candidato = Candidato.query.get(candidato_id)
    if not candidato:
        raise CandidatoError("Candidato no encontrado")

    if candidato.eleccion.estado != "CONFIGURACION":
        raise CandidatoError("Solo se pueden editar candidatos mientras la elección está en CONFIGURACION")

    campos = (
        "sigla_partido", "nombre_partido", "nombres", "apellido_paterno",
        "apellido_materno", "formula_nombres", "formula_apellido_paterno",
        "logo_partido", "foto_candidato", "color_partido", "propuesta_breve", "activo",
    )
    for campo in campos:
        if campo in datos:
            setattr(candidato, campo, datos[campo])

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=candidato.eleccion_id,
        accion="CANDIDATO_ACTUALIZADO",
        descripcion=f"Candidato #{candidato.numero_lista} actualizado",
        ip=ip,
    )
    return candidato


def eliminar_candidato(candidato_id: int, usuario_id: int, ip: str | None = None):
    candidato = Candidato.query.get(candidato_id)
    if not candidato:
        raise CandidatoError("Candidato no encontrado")

    if candidato.eleccion.estado != "CONFIGURACION":
        raise CandidatoError("Solo se pueden eliminar candidatos mientras la elección está en CONFIGURACION")

    eleccion_id = candidato.eleccion_id
    numero = candidato.numero_lista
    db.session.delete(candidato)
    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion="CANDIDATO_ELIMINADO",
        descripcion=f"Candidato #{numero} eliminado",
        ip=ip,
    )


def listar_candidatos(eleccion_id: int, solo_activos: bool = True) -> list[Candidato]:
    query = Candidato.query.filter_by(eleccion_id=eleccion_id)
    if solo_activos:
        query = query.filter_by(activo=True)
    return query.order_by(Candidato.numero_lista).all()
