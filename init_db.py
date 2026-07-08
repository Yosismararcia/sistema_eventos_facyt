import os
import pymysql
import traceback  # Nos ayudará a ver la línea exacta del error
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
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

def crear_tablas():
    print("Iniciando la conexión con Aiven MySQL...")
    try:
        conexion = obtener_conexion()
        print("Conexión establecida con éxito.")
        
        with conexion.cursor() as cursor:
            # Desactivar verificación de llaves foráneas temporalmente
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # Borrar las tablas viejas si existían
            cursor.execute("DROP TABLE IF EXISTS eventos;")
            cursor.execute("DROP TABLE IF EXISTS espacios;")
            cursor.execute("DROP TABLE IF EXISTS usuarios;")
            
            # Reactivar la verificación
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("Limpieza de tablas antiguas completada.")

            # 1. Crear tabla de Usuarios (con Roles)
            cursor.execute("""
                CREATE TABLE usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    correo VARCHAR(100) NOT NULL UNIQUE,
                    contrasena_hash VARCHAR(255) NOT NULL,
                    rol ENUM('administrativo', 'estudiante', 'ponente', 'organizador') NOT NULL,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("Tabla 'usuarios' creada con éxito.")

            # 2. Crear tabla de Espacios Físicos
            cursor.execute("""
                CREATE TABLE espacios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    tipo VARCHAR(50) NOT NULL,
                    capacidad INT NOT NULL,
                    ubicacion VARCHAR(150) NOT NULL
                );
            """)
            print("Tabla 'espacios' creada con éxito.")

            # 3. Crear tabla de Eventos con estructura completa
            cursor.execute("""
                CREATE TABLE eventos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    titulo VARCHAR(150) NOT NULL,
                    responsable_id INT,
                    tipo_actividad VARCHAR(50) NOT NULL,
                    fecha DATE NOT NULL,
                    hora_inicio TIME NOT NULL,
                    hora_fin TIME NOT NULL,
                    estado ENUM('solicitado', 'en revisión', 'aprobado', 'programado', 'realizado', 'cancelado', 'rechazado') DEFAULT 'solicitado',
                    espacio_id INT,
                    FOREIGN KEY (responsable_id) REFERENCES usuarios(id) ON DELETE SET NULL,
                    FOREIGN KEY (espacio_id) REFERENCES espacios(id) ON DELETE SET NULL
                );
            """)
            print("Tabla 'eventos' creada con éxito.")

            # 4. Eliminar el trigger si ya existía
            cursor.execute("DROP TRIGGER IF EXISTS antes_de_insertar_evento;")

            # 5. TRIGGER: Evitar conflictos y solapamientos de horarios y espacios
            cursor.execute("""
                CREATE TRIGGER antes_de_insertar_evento
                BEFORE INSERT ON eventos
                FOR EACH ROW
                BEGIN
                    DECLARE choques INT;
                    
                    SELECT COUNT(*) INTO choques
                    FROM eventos
                    WHERE espacio_id = NEW.espacio_id
                      AND fecha = NEW.fecha
                      AND estado IN ('aprobado', 'programado')
                      AND (
                          (NEW.hora_inicio >= hora_inicio AND NEW.hora_inicio < hora_fin) OR
                          (NEW.hora_fin > hora_inicio AND NEW.hora_fin <= hora_fin) OR
                          (NEW.hora_inicio <= hora_inicio AND NEW.hora_fin >= hora_fin)
                      );
                      
                    IF choques > 0 THEN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Error: Conflicto de horario. El espacio ya está reservado en ese rango de tiempo.';
                    END IF;
                END;
            """)
            print("Trigger de prevención de conflictos horaria configurado con éxito.")
            
        conexion.commit()
        print("¡Todo el proceso se guardó en la base de datos de manera exitosa!")
    except Exception as e:
        print("\n OCURRIÓ UN ERROR AL CONFIGURAR LA BASE DE DATOS:")
        traceback.print_exc()  # Esto imprimirá exactamente qué falló y en qué línea
    finally:
        if 'conexion' in locals() and conexion.open:
            conexion.close()
            print("Conexión cerrada.")

if __name__ == '__main__':
    crear_tablas()