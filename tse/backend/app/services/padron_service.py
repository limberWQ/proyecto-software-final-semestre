from datetime import date

from app.extensions import db
from app.models import PadronElectoral, Eleccion, Recinto
from app.services import segip_service
from app.services.audit_service import registrar_evento


class PadronError(Exception):
    pass


def _calcular_edad(fecha_nacimiento: date, referencia: date) -> int:
    edad = referencia.year - fecha_nacimiento.year
    if (referencia.month, referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


def _cumple_requisitos(ciudadano: dict, eleccion: Eleccion) -> tuple[bool, str | None]:
    """
    Verifica que el ciudadano del SEGIP cumpla los requisitos para
    entrar al padrón de esta elección:
      - debe estar vivo
      - debe tener 18 años cumplidos a más tardar el día de la votación
        (fecha_inicio de la elección)
      - debe pertenecer al mismo departamento que la elección
    """
    if not ciudadano.get("vivo", True):
        return False, "Ciudadano registrado como fallecido en SEGIP"

    fecha_nac = ciudadano.get("fecha_nacimiento")
    if isinstance(fecha_nac, str):
        fecha_nac = date.fromisoformat(fecha_nac[:10])

    fecha_votacion = eleccion.fecha_inicio.date()
    edad = _calcular_edad(fecha_nac, fecha_votacion)
    if edad < 18:
        return False, f"No cumple 18 años a la fecha de votación (edad calculada: {edad})"

    if int(ciudadano.get("departamento_id")) != int(eleccion.departamento_id):
        return False, "El ciudadano no corresponde al departamento de esta elección"

    return True, None


def construir_padron(eleccion_id: int, usuario_id: int, ip: str | None = None) -> dict:
    """
    Botón "Consultar y agregar usuarios habilitados":
    Consulta TODOS los ciudadanos del SEGIP, filtra los que pertenecen
    al departamento de la elección, son mayores de 18 (a la fecha de la
    votación) y están vivos, e inserta los nuevos en padron_electoral.

    No duplica registros ya existentes (UNIQUE ci+eleccion_id).
    Devuelve un resumen con totales.
    """
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise PadronError("Elección no encontrada")

    ciudadanos = segip_service.obtener_todos_ciudadanos()

    existentes = {
        p.ci for p in PadronElectoral.query.filter_by(eleccion_id=eleccion_id).all()
    }

    agregados = 0
    rechazados = 0
    omitidos_existentes = 0

    for c in ciudadanos:
        ci = c["ci"]
        if ci in existentes:
            omitidos_existentes += 1
            continue

        cumple, motivo = _cumple_requisitos(c, eleccion)
        if not cumple:
            rechazados += 1
            continue

        fecha_nac = c["fecha_nacimiento"]
        if isinstance(fecha_nac, str):
            fecha_nac = date.fromisoformat(fecha_nac[:10])

        registro = PadronElectoral(
            eleccion_id=eleccion_id,
            ci=ci,
            complemento=c.get("complemento"),
            nombres=c["nombres"],
            apellido_paterno=c["apellido_paterno"],
            apellido_materno=c.get("apellido_materno"),
            fecha_nacimiento=fecha_nac,
            sexo=c["sexo"],
            departamento_id=c["departamento_id"],
            habilitado=True,
            ya_voto=False,
        )
        db.session.add(registro)
        agregados += 1

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion="PADRON_CONSTRUIDO",
        descripcion=(
            f"Padrón actualizado desde SEGIP: {agregados} agregados, "
            f"{rechazados} rechazados (edad/vivo/departamento), "
            f"{omitidos_existentes} ya existentes"
        ),
        ip=ip,
    )

    return {
        "agregados": agregados,
        "rechazados": rechazados,
        "omitidos_existentes": omitidos_existentes,
        "total_padron": PadronElectoral.query.filter_by(eleccion_id=eleccion_id).count(),
    }


def actualizar_padron(eleccion_id: int, usuario_id: int, ip: str | None = None) -> dict:
    """
    Botón "Actualizar padrón":
    Vuelve a consultar SEGIP y:
      - agrega ciudadanos nuevos que ahora cumplen requisitos
      - inhabilita (habilitado=False) a quienes ya estaban en el padrón
        pero el SEGIP ahora reporta como fallecidos
    No elimina registros (se conserva trazabilidad), solo actualiza estado.
    """
    eleccion = Eleccion.query.get(eleccion_id)
    if not eleccion:
        raise PadronError("Elección no encontrada")

    ciudadanos = segip_service.obtener_todos_ciudadanos()
    ciudadanos_por_ci = {c["ci"]: c for c in ciudadanos}

    padron_actual = PadronElectoral.query.filter_by(eleccion_id=eleccion_id).all()
    padron_por_ci = {p.ci: p for p in padron_actual}

    agregados = 0
    inhabilitados = 0
    rehabilitados = 0

    # 1. Revisar inhabilitaciones por defunción reportada en SEGIP
    for ci, registro in padron_por_ci.items():
        ciudadano = ciudadanos_por_ci.get(ci)
        if ciudadano is None:
            continue
        vivo = ciudadano.get("vivo", True)
        if not vivo and registro.habilitado:
            registro.habilitado = False
            registro.motivo_inhabilitacion = "SEGIP reporta ciudadano fallecido"
            inhabilitados += 1
        elif (
            vivo
            and not registro.habilitado
            and registro.motivo_inhabilitacion == "SEGIP reporta ciudadano fallecido"
        ):
            registro.habilitado = True
            registro.motivo_inhabilitacion = None
            rehabilitados += 1

    # 2. Agregar ciudadanos nuevos que cumplen requisitos
    for c in ciudadanos:
        ci = c["ci"]
        if ci in padron_por_ci:
            continue

        cumple, _ = _cumple_requisitos(c, eleccion)
        if not cumple:
            continue

        fecha_nac = c["fecha_nacimiento"]
        if isinstance(fecha_nac, str):
            fecha_nac = date.fromisoformat(fecha_nac[:10])

        registro = PadronElectoral(
            eleccion_id=eleccion_id,
            ci=ci,
            complemento=c.get("complemento"),
            nombres=c["nombres"],
            apellido_paterno=c["apellido_paterno"],
            apellido_materno=c.get("apellido_materno"),
            fecha_nacimiento=fecha_nac,
            sexo=c["sexo"],
            departamento_id=c["departamento_id"],
            habilitado=True,
            ya_voto=False,
        )
        db.session.add(registro)
        agregados += 1

    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=eleccion_id,
        accion="PADRON_ACTUALIZADO",
        descripcion=(
            f"Padrón sincronizado con SEGIP: {agregados} nuevos, "
            f"{inhabilitados} inhabilitados (fallecidos), "
            f"{rehabilitados} rehabilitados"
        ),
        ip=ip,
    )

    return {
        "agregados": agregados,
        "inhabilitados": inhabilitados,
        "rehabilitados": rehabilitados,
        "total_padron": PadronElectoral.query.filter_by(eleccion_id=eleccion_id).count(),
    }


def asignar_recinto(padron_id: int, recinto_id: int, mesa_numero: int, usuario_id: int, ip: str | None = None):
    """Asigna un recinto y mesa a un votante del padrón."""
    registro = PadronElectoral.query.get(padron_id)
    if not registro:
        raise PadronError("Registro de padrón no encontrado")

    recinto = Recinto.query.get(recinto_id)
    if not recinto:
        raise PadronError("Recinto no encontrado")

    registro.recinto_id = recinto_id
    registro.mesa_numero = mesa_numero
    db.session.commit()

    registrar_evento(
        usuario_id=usuario_id,
        eleccion_id=registro.eleccion_id,
        accion="PADRON_RECINTO_ASIGNADO",
        descripcion=f"CI {registro.ci} asignado a recinto {recinto.codigo}, mesa {mesa_numero}",
        ip=ip,
    )
    return registro


def buscar_votante(eleccion_id: int, ci: str) -> PadronElectoral | None:
    return PadronElectoral.query.filter_by(eleccion_id=eleccion_id, ci=ci).first()


def listar_padron(eleccion_id: int, recinto_id: int | None = None):
    query = PadronElectoral.query.filter_by(eleccion_id=eleccion_id)
    if recinto_id:
        query = query.filter_by(recinto_id=recinto_id)
    return query.order_by(PadronElectoral.apellido_paterno).all()
