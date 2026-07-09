import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

conexion = pymysql.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    port=int(os.getenv('DB_PORT')),
    database=os.getenv('DB_NAME'),
    ssl_verify_identity=False
)

try:
    with conexion.cursor() as cursor:
        # Añadimos la columna descripcion de tipo TEXT (permite parrafos largos)
        cursor.execute("ALTER TABLE eventos ADD COLUMN descripcion TEXT AFTER tipo_actividad;")
    conexion.commit()
    print("🎉 Columna 'descripcion' añadida con éxito a la base de datos en Aiven.")
except Exception as e:
    print(f"Nota/Error: {e} (Si ya existía, puedes ignorar este mensaje)")
finally:
    conexion.close()