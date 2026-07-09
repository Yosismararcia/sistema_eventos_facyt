import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
# Clave secreta para cifrar las cookies de sesión y activar mensajes flash
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'clave_secreta_super_segura_facyt_2026')

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

# --- RUTA: INICIO (DASHBOARD) ---
@app.route('/')
def inicio():
    conexion = obtener_conexion()
    metrics = {'programados': 0, 'pendientes': 0, 'espacios': 0}
    eventos = []
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM eventos WHERE estado IN ('aprobado', 'programado');")
            metrics['programados'] = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) AS total FROM eventos WHERE estado IN ('solicitado', 'en revisión');")
            metrics['pendientes'] = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) AS total FROM espacios;")
            metrics['espacios'] = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, esp.nombre AS espacio, u.nombre AS responsable
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.estado IN ('aprobado', 'programado')
                ORDER BY e.fecha ASC LIMIT 5;
            """)
            eventos = cursor.fetchall()
    except Exception as e:
        print(f"Error al cargar el dashboard: {e}")
    finally:
        conexion.close()
    return render_template('index.html', metrics=metrics, eventos=eventos)


# --- RUTA: REGISTRO DE USUARIOS ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        rol = request.form.get('rol')
        contrasena = request.form.get('contrasena')

        if not all([nombre, correo, rol, contrasena]):
            flash("Error: Todos los campos son obligatorios.", "error")
            return redirect(url_for('registro'))

        # Encriptar la contraseña usando el método pbkdf2:sha256 por defecto
        contrasena_hash = generate_password_hash(contrasena)

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (nombre, correo, contrasena_hash, rol)
                    VALUES (%s, %s, %s, %s);
                """, (nombre, correo, contrasena_hash, rol))
            conexion.commit()
            flash("🎉 ¡Cuenta creada con éxito! Ahora puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        except pymysql.err.IntegrityError:
            # Captura si el correo electrónico ya existe (restricción UNIQUE de la BD)
            flash("Error: El correo electrónico ya se encuentra registrado.", "error")
        except Exception as e:
            flash(f"Error inesperado: {e}", "error")
        finally:
            conexion.close()
            
        return redirect(url_for('registro'))

    return render_template('registro.html')


# --- RUTA: INICIO DE SESIÓN (LOGIN) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')

        if not correo or not contrasena:
            flash("Error: Por favor rellene todos los campos.", "error")
            return redirect(url_for('login'))

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE correo = %s;", (correo,))
                usuario = cursor.fetchone()

            # Verificar si el usuario existe y si la contraseña coincide con el hash guardado
            if usuario and check_password_hash(usuario['contrasena_hash'], contrasena):
                # Guardar datos esenciales en la sesión del navegador
                session['usuario_id'] = usuario['id']
                session['usuario_nombre'] = usuario['nombre']
                session['usuario_rol'] = usuario['rol']
                
                flash(f"¡Bienvenido de nuevo, {usuario['nombre']}! 👋", "success")
                return redirect(url_for('inicio'))
            else:
                flash("Error: Credenciales incorrectas. Verifique correo y contraseña.", "error")
        except Exception as e:
            flash(f"Error del sistema: {e}", "error")
        finally:
            conexion.close()

        return redirect(url_for('login'))

    return render_template('login.html')


# --- RUTA: CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear() # Limpia todas las variables de sesión del usuario
    flash("Has cerrado sesión de forma segura.", "success")
    return redirect(url_for('inicio'))


# --- RUTA: SOLICITAR EVENTO (ACTUALIZADA) ---
@app.route('/solicitar', methods=['GET', 'POST'])
def solicitar():
    # Restricción: Si no ha iniciado sesión, no puede solicitar eventos
    if 'usuario_id' not in session:
        flash("Por favor, inicia sesión para poder solicitar un espacio.", "error")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        tipo_actividad = request.form.get('tipo_actividad')
        espacio_id = request.form.get('espacio_id')
        fecha = request.form.get('fecha')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        
        if not all([titulo, tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin]):
            flash("Error: Todos los campos son obligatorios.", "error")
            return redirect(url_for('solicitar'))
            
        if hora_inicio >= hora_fin:
            flash("Error lógico: La hora de inicio no puede ser mayor o igual a la de finalización.", "error")
            return redirect(url_for('solicitar'))

        try:
            with conexion.cursor() as cursor:
                # Modificado: Ahora el responsable_id es el ID real del usuario en sesión
                cursor.execute("""
                    INSERT INTO eventos (titulo, responsable_id, tipo_actividad, fecha, hora_inicio, hora_fin, estado, espacio_id)
                    VALUES (%s, %s, %s, %s, %s, %s, 'solicitado', %s);
                """, (titulo, session['usuario_id'], tipo_actividad, fecha, hora_inicio, hora_fin, espacio_id))
            conexion.commit()
            flash("¡Solicitud registrada correctamente! Queda en espera de revisión.", "success")
            return redirect(url_for('inicio'))
        except pymysql.MySQLError as e:
            if e.args[0] == 45000:
                flash(f"{e.args[1]}", "error")
            else:
                flash(f"Error inesperado en la base de datos: {e}", "error")
        finally:
            conexion.close()
        return redirect(url_for('solicitar'))

    espacios = []
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre, capacidad FROM espacios;")
            espacios = cursor.fetchall()
    except Exception as e:
        print(f"Error al traer espacios: {e}")
    finally:
        conexion.close()
        
    return render_template('solicitar.html', espacios=espacios)

#nueva modificacion para admin
# --- RUTA: PANEL DE ADMINISTRACIÓN ---
@app.route('/admin')
def admin_panel():
    # 1. Protección de Rol: Si no ha iniciado sesión o no es administrativo, denegar acceso
    if 'usuario_id' not in session or session.get('usuario_role') != 'administrativo' and session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado: Se requieren permisos administrativos.", "error")
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    solicitudes = []
    try:
        with conexion.cursor() as cursor:
            # Traer los eventos que están pendientes de gestión (solicitado, en revisión)
            cursor.execute("""
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, e.estado, 
                       esp.nombre AS espacio, u.nombre AS responsable
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.estado IN ('solicitado', 'en revisión')
                ORDER BY e.fecha ASC;
            """)
            solicitudes = cursor.fetchall()
    except Exception as e:
        print(f"Error al cargar solicitudes de administración: {e}")
    finally:
        conexion.close()

    return render_template('admin.html', solicitudes=solicitudes)


# --- RUTA: ACCIÓN DE MODERACIÓN (CAMBIAR ESTADO) ---
@app.route('/admin/moderar/<int:evento_id>', methods=['POST'])
def moderar_evento(evento_id):
    # Protección de Rol
    if 'usuario_id' not in session or session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado.", "error")
        return redirect(url_for('inicio'))

    nuevo_estado = request.form.get('nuevo_estado')
    
    if not nuevo_estado:
        flash("Por favor, seleccione un estado válido.", "error")
        return redirect(url_for('admin_panel'))

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Actualizamos el estado del evento seleccionado
            cursor.execute("UPDATE eventos SET estado = %s WHERE id = %s;", (nuevo_estado, evento_id))
        conexion.commit()
        flash(f"¡El evento ha sido actualizado a '{nuevo_estado}' con éxito!", "success")
    except pymysql.MySQLError as e:
        # Si el administrador intenta cambiar a 'aprobado' o 'programado' y CHOCA con otro evento, el Trigger saltará aquí
        if e.args[0] == 45000:
            flash(f"No se pudo aprobar: {e.args[1]}", "error")
        else:
            flash(f"Error en la base de datos: {e}", "error")
    except Exception as e:
        flash(f"Error inesperado: {e}", "error")
    finally:
        conexion.close()

    return redirect(url_for('admin_panel'))

# --- RUTA: HISTORIAL DE SOLICITUDES DEL USUARIO LOGUEADO ---
@app.route('/mis-solicitudes')
def mis_solicitudes():
    # Protección: Si no ha iniciado sesión, redirigir
    if 'usuario_id' not in session:
        flash("Por favor, inicia sesión para ver tus solicitudes.", "error")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    solicitudes = []
    try:
        with conexion.cursor() as cursor:
            # Buscamos solo los eventos creados por el ID en sesión
            cursor.execute("""
                SELECT e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, e.estado, esp.nombre AS espacio
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.responsable_id = %s
                ORDER BY e.fecha DESC;
            """, (session['usuario_id'],))
            solicitudes = cursor.fetchall()
    except Exception as e:
        print(f"Error al cargar mis solicitudes: {e}")
    finally:
        conexion.close()

    return render_template('mis_solicitudes.html', solicitudes=solicitudes)
    
if __name__ == '__main__':
    app.run(debug=True)