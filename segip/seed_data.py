# Llenado de datos de prueba en segip_db (ejecutar dentro del contenedor segip)

from datetime import date
import random

from app import app
from models import db, Ciudadano, Biometria

nombres = ["Juan", "Maria", "Carlos", "Ana", "Luis", "Sofia", "Miguel", "Lucia"]
apellidos = ["Perez", "Gomez", "Flores", "Mamani", "Quispe", "Rojas", "Lopez", "Torrez"]
departamentos_ids = list(range(1, 10))


def run_seed():
    with app.app_context():
        print("Limpiando datos...")
        Biometria.query.delete()
        Ciudadano.query.delete()
        db.session.commit()

        print("Insertando ciudadanos...")
        for i in range(1, 51):
            ci = str(1000000 + i)

            # La mayoría son mayores de 18 años (nacidos antes de 2008);
            # algunos serán menores de 18 para probar el filtro de edad
            # del padrón electoral del TSE.
            if i % 10 == 0:
                anio_nac = random.randint(2009, 2012)  # menor de 18
            else:
                anio_nac = random.randint(1955, 2007)

            ciudadano = Ciudadano(
                ci=ci,
                complemento="",
                nombres=random.choice(nombres),
                apellido_paterno=random.choice(apellidos),
                apellido_materno=random.choice(apellidos),
                fecha_nacimiento=date(anio_nac, random.randint(1, 12), random.randint(1, 28)),
                lugar_nacimiento="Bolivia",
                sexo=random.choice(["M", "F"]),
                estado_civil=random.choice(["SOLTERO", "CASADO", "DIVORCIADO"]),
                departamento_id=random.choice(departamentos_ids),
                municipio="Municipio " + str(random.randint(1, 20)),
                domicilio="Zona " + str(random.randint(1, 50)),
                vivo=True if i != 5 else False,  # uno fallecido para pruebas
                activo=True
            )

            db.session.add(ciudadano)
            db.session.flush()

            bio = Biometria(
                ciudadano_id=ciudadano.id,
                foto_hash=f"foto_{ci}",
                huella_hash=f"huella_{ci}"
            )
            db.session.add(bio)

        db.session.commit()
        print("Seed completado")


if __name__ == "__main__":
    run_seed()
