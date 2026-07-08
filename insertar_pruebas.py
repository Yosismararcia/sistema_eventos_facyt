import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def obtener_conexion():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=int(os.getenv('DB_PORT')),
        database=os.getenv('DB_NAME'),
        ssl_verify_identity=False
    )

def registrar_datos_prueba():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            print("Iniciando inserción de datos de prueba...")
            
            # 1. Insertar un Usuario (Responsable/Administrativo) si no existe
            cursor.execute("""
                INSERT INTO usuarios (id, nombre, correo, contrasena_hash, rol)
                VALUES (1, 'Prof. Carlos Martínez', 'carlos.martinez@uc.edu.ve', 'hash_simulado_123', 'administrativo')
                ON DUPLICATE KEY UPDATE nombre=nombre;
            """)
            
            # 2. Insertar Espacios Físicos de la FaCyT
            cursor.execute("""
                INSERT INTO espacios (id, nombre, tipo, capacidad, ubicacion)
                VALUES 
                (1, 'Auditorio Benito Pereda', 'Auditorio', 150, 'Edificio de Química, Planta Baja'),
                (2, 'Laboratorio de Computación 1', 'Laboratorio', 30, 'Edificio de Computación, Piso 1')
                ON DUPLICATE KEY UPDATE nombre=nombre;
            """)
            print("✔ Espacios físicos registrados.")
            
            # 3. Insertar un Evento de Prueba aprobado (Jornadas de Investigación)
            # Nota: Asegúrate de poner una fecha futura si deseas simular eventos próximos
            cursor.execute("""
                INSERT INTO eventos (titulo, responsable_id, tipo_actividad, fecha, hora_inicio, hora_fin, estado, espacio_id)
                VALUES ('Congreso de Ciencia y Tecnología FaCyT 2026', 1, 'Congreso', '2026-11-15', '09:00:00', '13:00:00', 'programado', 1);
            """)
            print("✔ Evento de prueba registrado con éxito.")
            
        conexion.commit()
        print("🎉 ¡Todos los datos de prueba han sido inyectados con éxito en Aiven!")
    except Exception as e:
        print(f"Error al insertar datos: {e}")
    finally:
        conexion.close()

if __name__ == '__main__':
    registrar_datos_prueba()