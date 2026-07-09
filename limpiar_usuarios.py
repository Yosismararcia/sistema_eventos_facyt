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
        # Desactivamos temporalmente la verificación de llaves foráneas para no truncar datos en cascada
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        # Limpiamos las tablas de usuarios e inscripciones para empezar las pruebas desde cero de forma limpia
        cursor.execute("TRUNCATE TABLE usuarios;")
        cursor.execute("TRUNCATE TABLE inscripciones;")
        cursor.execute("TRUNCATE TABLE propuestas_estudiantes;")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conexion.commit()
    print("🧹 Base de datos de usuarios e inscripciones vaciada con éxito. ¡Listo para pruebas limpias!")
except Exception as e:
    print(f"❌ Error al limpiar: {e}")
finally:
    conexion.close()