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
        # 1. Crear tabla de nómina/personal autorizado por cédula
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personal_autorizado (
                cedula VARCHAR(20) PRIMARY KEY,
                nombre_completo VARCHAR(100) NOT NULL,
                rol_permitido VARCHAR(30) NOT NULL
            );
        """)
        
        # Insertamos profesores y admin de prueba con cédulas ficticias (puedes cambiarlas)
        cursor.execute("INSERT IGNORE INTO personal_autorizado VALUES ('V-27894120', 'Admin. yosismar arcia', 'administrativo');")
        cursor.execute("INSERT IGNORE INTO personal_autorizado VALUES ('V-12345678', 'Ing. María Alejandra', 'ponente');")

        # 2. Modificar la tabla de usuarios para incluir la cédula
        cursor.execute("ALTER TABLE usuarios ADD COLUMN cedula VARCHAR(20) UNIQUE AFTER nombre;")

        # 3. Crear la tabla de propuestas de estudiantes (sin fecha, hora ni salón asignado)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS propuestas_estudiantes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                estudiante_id INT NOT NULL,
                titulo VARCHAR(150) NOT NULL,
                tipo_actividad VARCHAR(50) NOT NULL,
                descripcion TEXT NOT NULL,
                fecha_propuesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (estudiante_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
        """)
        
    conexion.commit()
    print("🎉 Base de datos adaptada con éxito al sistema de Cédulas y Propuestas.")
except Exception as e:
    print(f"Nota/Error durante la migración: {e}")
finally:
    conexion.close()