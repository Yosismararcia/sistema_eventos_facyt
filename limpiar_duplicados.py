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
        ssl_verify_identity=False,
        cursorclass=pymysql.cursors.DictCursor
    )

def limpiar_por_horario():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # 1. Agrupamos por salón, fecha y hora para encontrar los que se solapan
            cursor.execute("""
                SELECT espacio_id, fecha, hora_inicio, COUNT(*) as total, MAX(id) as id_mas_nuevo
                FROM eventos
                GROUP BY espacio_id, fecha, hora_inicio
                HAVING COUNT(*) > 1;
            """)
            duplicados = cursor.fetchall()
            
            if duplicados:
                for dup in duplicados:
                    id_a_borrar = dup['id_mas_nuevo']
                    # 2. Borramos directamente usando el ID numérico (que nunca falla)
                    cursor.execute("DELETE FROM eventos WHERE id = %s;", (id_a_borrar,))
                    print(f"✔ Eliminado con éxito el evento repetido con ID: {id_a_borrar}")
                conexion.commit()
                print("🎉 ¡Limpieza terminada con éxito!")
            else:
                print("No se encontraron eventos duplicados compartiendo el mismo salón, fecha y hora.")
                
    except Exception as e:
        print(f"❌ Error al limpiar: {e}")
    finally:
        conexion.close()

if __name__ == '__main__':
    limpiar_por_horario()