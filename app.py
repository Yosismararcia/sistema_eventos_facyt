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

#Ruta para registro de  usuarios (modificado para validar cédula de ponentes y administrativos)
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        cedula = request.form.get('cedula').strip()
        correo = request.form.get('correo')
        password = request.form.get('password')
        rol = request.form.get('rol')

        # VALIDACIÓN INSTITUCIONAL DE CÉDULA
        if rol in ['ponente', 'administrativo']:
            conexion = obtener_conexion()
            try:
                with conexion.cursor() as cursor:
                    # Buscamos si la cédula existe y corresponde al rol seleccionado
                    cursor.execute("SELECT * FROM personal_autorizado WHERE cedula = %s AND rol_permitido = %s;", (cedula, rol))
                    autorizado = cursor.fetchone()
                    if not autorizado:
                        flash(f"❌ Acceso Denegado: La cédula {cedula} no está registrada como personal autorizado para el rol de {rol}.", "error")
                        return redirect(url_for('registro'))
            finally:
                conexion.close()

        # Si pasa la validación o es estudiante, se registra
        password_hashed = generate_password_hash(password)
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (nombre, cedula, correo, password, rol)
                    VALUES (%s, %s, %s, %s, %s);
                """, (nombre, cedula, correo, password_hashed, rol))
            conexion.commit()
            flash("🎉 Cuenta creada con éxito. Ya puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("Error: La cédula o el correo ya se encuentran registrados en el sistema.", "error")
        finally:
            conexion.close()

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
# --- RUTA: PANEL ADMINISTRATIVO CON ESTADÍSTICAS ---
@app.route('/admin')
# --- RUTA: PANEL ADMINISTRATIVO CON ESTADÍSTICAS Y PROPUESTAS ---
@app.route('/admin')
def admin():
    # Protección estricta de rol: Solo entra el administrativo
    if 'usuario_id' not in session or session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado. Se requieren permisos de administrador.", "error")
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    solicitudes = []
    propuestas = [] # <- Nueva lista para las ideas de los alumnos
    top_espacios = []
    conteo_estados = []

    try:
        with conexion.cursor() as cursor:
            # 1. Consulta de solicitudes formales (hechas por profesores/ponentes)
            cursor.execute("""
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, e.estado, 
                       esp.nombre AS espacio, u.nombre AS solicitado_por
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                ORDER BY e.fecha ASC;
            """)
            solicitudes = cursor.fetchall()

            # 2. NUEVA CONSULTA: Traer las propuestas enviadas por los estudiantes
            cursor.execute("""
                SELECT p.id, p.titulo, p.tipo_actividad, p.descripcion, u.nombre AS estudiante
                FROM propuestas_estudiantes p
                JOIN usuarios u ON p.estudiante_id = u.id
                ORDER BY p.id DESC;
            """)
            propuestas = cursor.fetchall()

            # 3. Estadística 1: Top espacios más solicitados
            cursor.execute("""
                SELECT esp.nombre, COUNT(e.id) as total 
                FROM eventos e
                JOIN espacios esp ON e.espacio_id = esp.id
                GROUP BY esp.nombre
                ORDER BY total DESC
                LIMIT 5;
            """)
            top_espacios = cursor.fetchall()

            # 4. Estadística 2: Cantidad de eventos por estado
            cursor.execute("""
                SELECT estado, COUNT(*) as total 
                FROM eventos 
                GROUP BY estado;
            """)
            conteo_estados = cursor.fetchall()

    except Exception as e:
        print(f"Error en panel administrativo: {e}")
    finally:
        conexion.close()

    # Enviamos de forma explícita 'propuestas' al HTML
    return render_template('admin.html', 
                           solicitudes=solicitudes, 
                           propuestas=propuestas, 
                           top_espacios=top_espacios, 
                           conteo_estados=conteo_estados)

# --- modificacion de el estado de las solicitudes por el admin ---
@app.route('/admin/actualizar-estado/<int:evento_id>', methods=['POST'])
def admin_actualizar_estado(evento_id):
    # 1. Protección de seguridad: Verificar que sea un usuario administrativo
    if 'usuario_id' not in session or session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado. Se requieren permisos de administrador.", "error")
        return redirect(url_for('inicio'))

    # 2. Capturar el estado seleccionado por el administrador en el menú desplegable
    nuevo_estado = request.form.get('estado')
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Consultamos primero los datos del evento para saber el título y quién es el solicitante
            cursor.execute("""
                SELECT e.titulo, u.nombre AS solicitante 
                FROM eventos e
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.id = %s;
            """, (evento_id,))
            datos_evento = cursor.fetchone()
            
            if datos_evento:
                titulo_evento = datos_evento['titulo']
                nombre_solicitante = datos_evento['solicitante'] if datos_evento['solicitante'] else "el ponente asignado"
            else:
                titulo_evento = f"Evento #{evento_id}"
                nombre_solicitante = "el solicitante"

            # 3. Ejecutar la actualización en la base de datos
            cursor.execute("UPDATE eventos SET estado = %s WHERE id = %s;", (nuevo_estado, evento_id))
        
        # Guardar cambios permanentemente
        conexion.commit()
        
        # 4. Mensaje de éxito que indica explícitamente a quién afectó el cambio de estado
        flash(f"📢 Control de Estado: El evento '{titulo_evento}' ha sido actualizado a '{nuevo_estado.upper()}'. "
              f"Se ha modificado el estado formal en el historial de {nombre_solicitante}.", "success")

    except pymysql.MySQLError as e:
        # Si pasa a 'aprobado' o 'programado' y CHOCA en horario/salón, el Trigger de la FaCyT salta aquí:
        if e.args[0] == 45000:
            flash(f"❌ Error de Validación: {e.args[1]}", "error")
        else:
            flash(f"❌ Error en la base de datos al guardar: {e}", "error")
    except Exception as e:
        flash(f"❌ Error inesperado: {e}", "error")
    finally:
        conexion.close()

    # Redirigir de vuelta al panel administrativo para mostrar la alerta
    return redirect(url_for('admin'))

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
    
# ---- RUTA PARA PROPUESTAS DE ESTUDIANTES
@app.route('/proponer', methods=['GET', 'POST'])
def proponer_evento():
    if 'usuario_id' not in session or session.get('usuario_rol') != 'estudiante':
        flash("Esta sección es exclusiva para que los estudiantes propongan ideas.", "error")
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        tipo_actividad = request.form.get('tipo_actividad')
        descripcion = request.form.get('descripcion')

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO propuestas_estudiantes (estudiante_id, titulo, tipo_actividad, descripcion)
                    VALUES (%s, %s, %s, %s);
                """, (session['usuario_id'], titulo, tipo_actividad, descripcion))
            conexion.commit()
            flash("💡 ¡Tu propuesta ha sido enviada con éxito al profesorado! Gracias por contribuir.", "success")
            return redirect(url_for('inicio'))
        except Exception as e:
            flash(f"Hubo un error al procesar tu propuesta: {e}", "error")
        finally:
            conexion.close()

    return render_template('proponer.html')

## --- RUTA: ELIMINAR EVENTO (SOLO ADMIN) ---
@app.route('/admin/eliminar-evento/<int:evento_id>', methods=['POST'])
def admin_eliminar_evento(evento_id):
    if 'usuario_id' not in session or session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado.", "error")
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM eventos WHERE id = %s;", (evento_id,))
        conexion.commit()
        flash("🗑️ El evento ha sido eliminado permanentemente del sistema.", "success")
    except Exception as e:
        flash(f"Error al eliminar el evento: {e}", "error")
    finally:
        conexion.close()
        
    return redirect(url_for('admin'))

# --- RUTA: EDITAR EVENTO (FORMULARIO Y PROCESAMIENTO) ---
@app.route('/admin/editar-evento/<int:evento_id>', methods=['GET', 'POST'])
def admin_editar_evento(evento_id):
    if 'usuario_id' not in session or session.get('usuario_rol') != 'administrativo':
        flash("Acceso denegado.", "error")
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    if request.method == 'POST':
        nuevo_titulo = request.form.get('titulo')
        nuevo_tipo = request.form.get('tipo_actividad')
        
        try:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    UPDATE eventos 
                    SET titulo = %s, tipo_actividad = %s 
                    WHERE id = %s;
                """, (nuevo_titulo, nuevo_tipo, evento_id))
            conexion.commit()
            flash("✏️ El evento ha sido modificado con éxito.", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            flash(f"Error al actualizar datos: {e}", "error")
        finally:
            conexion.close()

    # Método GET: Buscar los datos actuales para mostrarlos en el formulario
    evento = None
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, titulo, tipo_actividad FROM eventos WHERE id = %s;", (evento_id,))
            evento = cursor.fetchone()
    finally:
        conexion.close()

    if not evento:
        flash("El evento no existe.", "error")
        return redirect(url_for('admin'))

    return render_template('editar_evento.html', evento=evento)






if __name__ == '__main__':
    app.run(debug=True)