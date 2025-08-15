# ============================================================================
# SISTEMA DE ALERTA VECINAL - SERVIDOR FLASK
# ============================================================================
# Este servidor maneja todo el sistema de alertas vecinales, incluyendo:
# - Webhook de Telegram para recibir comandos
# - API para enviar alertas de emergencia
# - Llamadas telefónicas automáticas con Twilio
# - Gestión de comunidades y miembros
# ============================================================================

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from datetime import datetime
import os
import json
import requests

# 📦 Twilio para llamadas telefónicas automáticas
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

# ============================================================================
# CONFIGURACIÓN INICIAL DEL SERVIDOR
# ============================================================================

app = Flask(__name__)
CORS(app)  # Permite peticiones desde cualquier origen (necesario para WebApps)

# 📁 Ruta donde están almacenados los archivos JSON de cada comunidad
# Cada comunidad tiene su propio archivo JSON con datos de miembros
DATA_FILE = os.path.join(os.path.dirname(__file__), 'comunidades')

# 🔑 Variables de entorno para credenciales de servicios externos
# Estas se configuran en Railway/Heroku y nunca se hardcodean
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')  # ID de cuenta Twilio
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')    # Token de autenticación Twilio
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')  # Número desde el cual llamar

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Token del bot de Telegram

# 🌐 URL base del servidor (se usa para generar links de WebApp)
# En producción será algo como https://tu-app.railway.app
BASE_URL = os.getenv('BASE_URL', 'https://tu-servidor.com')

# 🎯 Cliente de Twilio para realizar llamadas telefónicas
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ============================================================================
# SISTEMA DE SEGUIMIENTO DE USUARIOS
# ============================================================================
# Este diccionario es CLAVE para resolver el problema original
# Almacena temporalmente qué usuario específico activó SOS en cada comunidad
# 
# Estructura: {'nombre_comunidad': telegram_user_id}
# Ejemplo: {'villa': 1667177404, 'sanjuan': 9876543210}
# 
# ¿Por qué es necesario?
# - Cuando un usuario escribe "SOS", necesitamos recordar quién fue
# - Cuando se envía la alerta después, usamos esta info para identificarlo
# - Se limpia automáticamente después de usar para evitar conflictos
usuarios_sos_activos = {}

# ============================================================================
# RUTAS DEL SERVIDOR WEB
# ============================================================================

# 🌐 Ruta principal - Sirve la página HTML del botón de emergencia
@app.route('/')
def index():
    """
    Sirve el archivo index.html que contiene el formulario de emergencia
    Esta página se abre cuando el usuario hace click en el botón de Telegram
    """
    return render_template('index.html')

# 🔍 API para obtener lista de todas las comunidades disponibles
@app.route('/api/comunidades')
def listar_comunidades():
    """
    Devuelve un JSON con todas las comunidades disponibles
    Lee todos los archivos .json en la carpeta 'comunidades'
    
    Ejemplo de respuesta: ["villa", "sanjuan", "pueblo_libre"]
    """
    comunidades = []
    if os.path.exists(DATA_FILE):
        # Recorre todos los archivos en la carpeta comunidades
        for archivo in os.listdir(DATA_FILE):
            if archivo.endswith('.json'):  # Solo archivos JSON
                # Remueve la extensión .json para obtener el nombre de la comunidad
                comunidades.append(archivo.replace('.json', ''))
    return jsonify(comunidades)

# 📍 API para obtener miembros de una comunidad específica
@app.route('/api/ubicaciones/<comunidad>')
def ubicaciones_de_comunidad(comunidad):
    """
    Devuelve la información de todos los miembros de una comunidad
    
    Args:
        comunidad (str): Nombre de la comunidad (ej: "villa")
    
    Returns:
        JSON con lista de miembros o error 404 si no existe
    
    Ejemplo de uso: GET /api/ubicaciones/villa
    """
    # Construye la ruta al archivo JSON de la comunidad
    path = os.path.join(DATA_FILE, f"{comunidad}.json")
    
    # Verifica si el archivo existe
    if not os.path.exists(path):
        return jsonify({"error": "Comunidad no encontrada"}), 404
    
    # Lee y parsea el archivo JSON
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Maneja diferentes estructuras de JSON
    if isinstance(data, dict):
        # Si es un diccionario, busca la clave "miembros"
        return jsonify(data.get("miembros", []))
    else:
        # Si es una lista directa, la devuelve tal como está
        return jsonify(data)

# ============================================================================
# ENDPOINT PRINCIPAL - PROCESAMIENTO DE ALERTAS
# ============================================================================

@app.route('/api/alert', methods=['POST'])
def recibir_alerta():
    """
    🚨 ENDPOINT MÁS IMPORTANTE DEL SISTEMA 🚨
    
    Recibe una alerta de emergencia y realiza todas las acciones necesarias:
    1. Identifica al usuario que envió la alerta
    2. Envía mensaje a Telegram con todos los detalles
    3. Realiza llamadas automáticas a todos los miembros
    4. Registra la actividad en logs
    
    Este endpoint es llamado desde script.js cuando el usuario presiona
    el botón "Enviar Alerta Roja"
    """
    
    # ========================================================================
    # PASO 1: RECEPCIÓN Y VALIDACIÓN DE DATOS
    # ========================================================================
    
    # Obtiene los datos JSON enviados desde el navegador
    data = request.get_json()
    print("📦 Datos recibidos:", data)  # Log para debugging

    # Extrae cada campo del JSON recibido
    tipo = data.get('tipo')                    # Tipo de alerta (siempre "Alerta Roja Activada")
    descripcion = data.get('descripcion')      # Texto escrito por el usuario
    ubicacion = data.get('ubicacion', {})      # Coordenadas {lat, lon}
    direccion = data.get('direccion')          # Dirección del usuario
    comunidad = data.get('comunidad')          # Nombre de la comunidad
    telegram_user_id = data.get('telegram_user_id')  # 🎯 ID del usuario de Telegram (NUEVO)

    # Extrae coordenadas específicas
    lat = ubicacion.get('lat')  # Latitud
    lon = ubicacion.get('lon')  # Longitud

    # Validación básica - todos estos campos son obligatorios
    if not descripcion or not lat or not lon or not comunidad:
        return jsonify({'error': 'Faltan datos'}), 400

    # ========================================================================
    # PASO 2: CARGA DE DATOS DE LA COMUNIDAD
    # ========================================================================
    
    # Construye la ruta al archivo JSON de la comunidad
    archivo_comunidad = os.path.join(DATA_FILE, f"{comunidad}.json")
    
    # Verifica que la comunidad exista
    if not os.path.exists(archivo_comunidad):
        return jsonify({'error': 'Comunidad no encontrada'}), 404

    # Lee el archivo JSON con todos los datos de la comunidad
    with open(archivo_comunidad, 'r', encoding='utf-8') as f:
        datos_comunidad = json.load(f)

    # Extrae información específica del JSON
    miembros = datos_comunidad.get('miembros', [])           # Lista de todos los miembros
    telegram_chat_id = datos_comunidad.get('telegram_chat_id')  # ID del grupo de Telegram

    # ========================================================================
    # PASO 3: IDENTIFICACIÓN DEL USUARIO QUE REPORTA (PARTE CRUCIAL)
    # ========================================================================
    # Esta es la solución al problema original
    # Antes siempre usaba miembros[0], ahora identifica al usuario real
    
    miembro_reportante = None
    
    # 🎯 PRIORIDAD 1: Buscar por telegram_user_id enviado directamente
    # Esto sucede cuando el JavaScript logra capturar el user_id de la URL
    if telegram_user_id:
        print(f"🔍 Buscando usuario por Telegram ID: {telegram_user_id}")
        for miembro in miembros:
            # Compara los IDs (convertidos a string para evitar problemas de tipo)
            if str(miembro.get('telegram_id')) == str(telegram_user_id):
                miembro_reportante = miembro
                print(f"✅ Usuario encontrado por Telegram ID: {miembro['nombre']}")
                break
    
    # 🎯 PRIORIDAD 2: Buscar en usuarios_sos_activos
    # Esto sucede cuando el usuario escribió SOS y esa info se guardó temporalmente
    if not miembro_reportante and comunidad in usuarios_sos_activos:
        user_id_sos = usuarios_sos_activos[comunidad]
        print(f"🔍 Buscando usuario por SOS activo: {user_id_sos}")
        for miembro in miembros:
            if str(miembro.get('telegram_id')) == str(user_id_sos):
                miembro_reportante = miembro
                print(f"✅ Usuario encontrado por SOS activo: {miembro['nombre']}")
                # 🧹 IMPORTANTE: Limpiar el registro después de usar
                # Esto evita que se use para alertas futuras de otros usuarios
                del usuarios_sos_activos[comunidad]
                break
    
    # 🎯 FALLBACK: Si no se puede identificar, usar el primer miembro
    # Esto mantiene compatibilidad con versiones anteriores
    if not miembro_reportante and miembros:
        miembro_reportante = miembros[0]
        print("⚠️ No se pudo identificar al usuario específico, usando el primer miembro como fallback")
    
    # ========================================================================
    # PASO 4: PREPARACIÓN DE DATOS PARA LA NOTIFICACIÓN
    # ========================================================================
    
    # Usa los datos del miembro identificado (¡esta es la corrección principal!)
    if miembro_reportante:
        nombre_reportante = miembro_reportante.get('nombre', 'Usuario desconocido')
        direccion_reportante = miembro_reportante.get('direccion', direccion or 'Dirección no disponible')
        
        # 🎯 MANEJO DE GEOLOCALIZACIÓN
        # Si el usuario NO activó "ubicación en tiempo real", usar la predeterminada del JSON
        if not data.get('ubicacion_tiempo_real', False):
            geo_miembro = miembro_reportante.get('geolocalizacion', {})
            if geo_miembro:
                lat = geo_miembro.get('lat', lat)  # Usa coordenadas del JSON
                lon = geo_miembro.get('lon', lon)
    else:
        # Si no se encuentra ningún miembro, usar valores por defecto
        nombre_reportante = 'Usuario desconocido'
        direccion_reportante = direccion or 'Dirección no disponible'

    # ========================================================================
    # PASO 5: CREACIÓN DEL MENSAJE DE ALERTA
    # ========================================================================
    
    # Construye el mensaje HTML que se enviará a Telegram
    # Usa formato HTML para hacer el mensaje más legible y profesional
    mensaje = f"""
🚨 <b>ALERTA VECINAL</b> 🚨

<b>Comunidad:</b> {comunidad.upper()}
<b>👤 Reportado por:</b> {nombre_reportante}
<b>📍 Dirección:</b> {direccion_reportante}
<b>📝 Descripción:</b> {descripcion}
<b>📍 Ubicación:</b> https://maps.google.com/maps?q={lat},{lon}
<b>🕐 Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""

    # ========================================================================
    # PASO 6: ENVÍO DE NOTIFICACIONES
    # ========================================================================
    
    # 📱 Envía el mensaje al grupo de Telegram
    enviar_telegram(telegram_chat_id, mensaje)

    # 📞 Realiza llamadas automáticas a todos los miembros de la comunidad
    # Esto asegura que incluso si alguien no ve el mensaje de Telegram, reciba una llamada
    for miembro in miembros:
        telefono = miembro.get('telefono')
        if not telefono:
            continue  # Salta miembros sin teléfono
        
        try:
            # Crea una llamada automática con mensaje de voz en español
            client.calls.create(
                twiml='<Response><Say voice="alice" language="es-ES">Emergencia. Alarma vecinal. Revisa tu celular.</Say></Response>',
                from_=TWILIO_FROM_NUMBER,  # Número Twilio configurado
                to=telefono               # Número del miembro
            )
            print(f"📞 Llamada iniciada a {telefono}")
        except Exception as e:
            # Si falla una llamada, continúa con las demás
            print(f"❌ Error al llamar a {telefono}: {e}")

    # ========================================================================
    # PASO 7: RESPUESTA AL CLIENTE
    # ========================================================================
    
    # Responde al JavaScript que todo salió bien
    return jsonify({'status': f'Alerta enviada a la comunidad {comunidad}'}), 200

# ============================================================================
# WEBHOOK DE TELEGRAM - RECEPCIÓN DE COMANDOS
# ============================================================================

@app.route('/webhook/telegram', methods=['POST'])
def webhook_telegram():
    """
    🤖 WEBHOOK PRINCIPAL DE TELEGRAM 🤖
    
    Este endpoint recibe TODOS los mensajes enviados al bot de Telegram
    Telegram hace una petición POST aquí cada vez que alguien:
    - Escribe un mensaje al bot
    - Escribe un mensaje en un grupo donde está el bot
    - Presiona un botón inline
    - Etc.
    
    COMANDOS SOPORTADOS:
    - "sos" (sin barra): Activa el botón de emergencia
    - "MIREGISTRO2222": Registra al usuario en los logs
    """
    try:
        # ====================================================================
        # PASO 1: PROCESAMIENTO DEL WEBHOOK
        # ====================================================================
        
        # Obtiene los datos JSON enviados por Telegram
        data = request.get_json()
        print("📨 Webhook recibido:", data)  # Log completo para debugging
        
        # Verifica que sea un mensaje válido
        # Telegram puede enviar otros tipos de updates (inline queries, etc.)
        if 'message' not in data:
            return jsonify({'status': 'ok'})  # Ignora updates que no sean mensajes
        
        # ====================================================================
        # PASO 2: EXTRACCIÓN DE INFORMACIÓN DEL MENSAJE
        # ====================================================================
        
        message = data['message']
        chat_id = message['chat']['id']                    # ID del chat/grupo
        text = message.get('text', '').strip().lower()     # Texto del mensaje (en minúsculas)
        
        # Información del usuario que envió el mensaje
        user = message.get('from', {})
        user_id = user.get('id')                          # 🎯 ID único del usuario (CLAVE)
        first_name = user.get('first_name', 'Sin nombre') # Nombre del usuario
        username = user.get('username', 'Sin username')   # @username del usuario
        
        # ====================================================================
        # PASO 3: PROCESAMIENTO DEL COMANDO "SOS"
        # ====================================================================
        
        if text == 'sos':  # Usuario escribió "sos" (sin barra /)
            print(f"🚨 Comando SOS recibido de {first_name} (ID: {user_id})")
            
            # Busca a qué comunidad pertenece este chat
            comunidad = obtener_comunidad_por_chat_id(chat_id)
            
            if not comunidad:
                # Si el chat no está registrado en ninguna comunidad
                enviar_mensaje_telegram(chat_id, "❌ Este chat no está registrado en ninguna comunidad.")
                return jsonify({'status': 'ok'})
            
            # 🎯 PARTE CRUCIAL: GUARDAR QUIÉN ACTIVÓ SOS
            # Esto es lo que permite identificar al usuario después
            usuarios_sos_activos[comunidad] = user_id
            print(f"💾 SOS activado por usuario {first_name} (ID: {user_id}) en comunidad {comunidad}")
            
            # Crea la URL del WebApp incluyendo tanto la comunidad como el user_id
            # Esta URL es la que se abrirá cuando el usuario presione el botón
            webapp_url = f"{BASE_URL}?comunidad={comunidad}&user_id={user_id}"
            
            # Crea el botón inline que aparecerá en Telegram
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🚨 ABRIR BOTÓN DE EMERGENCIA 🚨",
                        "url": webapp_url  # Cuando se presiona, abre esta URL
                    }
                ]]
            }
            
            # Envía un mensaje con el botón
            mensaje_respuesta = "🚨"  # Mensaje simple pero efectivo
            enviar_mensaje_telegram(chat_id, mensaje_respuesta, keyboard)
        
        # ====================================================================
        # PASO 4: PROCESAMIENTO DEL COMANDO "MIREGISTRO2222"
        # ====================================================================
        
        elif text == 'miregistro2222':  # Comando especial para registrar usuarios
            # Registra información del usuario en los logs del servidor
            # Útil para debugging y administración
            chat_title = message.get('chat', {}).get('title', 'Chat privado')
            print(f"👤 REGISTRO: Usuario '{first_name}' (@{username}) - ID: {user_id} - Chat: {chat_title} ({chat_id})")
            
            # Mensaje de confirmación con formato ASCII art
            mensaje_registro = """  ┏━━━━━━━━━━━━━━━━━━━┓
  ┃  👐 REGISTRADO 👐  ┃
  ┗━━━━━━━━━━━━━━━━━━━┛
  🦾 Bienvenido al sistema 🦾"""
            
            # Envía la confirmación al usuario
            enviar_mensaje_telegram(chat_id, mensaje_registro)
        
        # Respuesta exitosa a Telegram (siempre devolver 200)
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        # Si algo sale mal, loggea el error pero responde OK a Telegram
        # Esto evita que Telegram reintente el webhook infinitamente
        print(f"❌ Error en webhook: {e}")
        return jsonify({'status': 'error'}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def obtener_comunidad_por_chat_id(chat_id):
    """
    🔍 FUNCIÓN CLAVE PARA IDENTIFICAR COMUNIDADES
    
    Busca qué comunidad corresponde a un chat_id específico de Telegram
    
    ¿Cómo funciona?
    1. Lee todos los archivos JSON de la carpeta 'comunidades'
    2. Busca el que tenga el telegram_chat_id coincidente
    3. Devuelve el nombre de esa comunidad
    
    Args:
        chat_id (int): ID del chat/grupo de Telegram
        
    Returns:
        str: Nombre de la comunidad o None si no se encuentra
        
    Ejemplo:
        chat_id = -1002525690225
        return = "villa"
    """
    if not os.path.exists(DATA_FILE):
        return None
    
    # Recorre todos los archivos JSON
    for archivo in os.listdir(DATA_FILE):
        if archivo.endswith('.json'):
            path = os.path.join(DATA_FILE, archivo)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Verifica si el telegram_chat_id coincide
                # Convierte ambos a string para evitar problemas de tipo
                if data.get('telegram_chat_id') == str(chat_id):
                    # Devuelve el nombre de la comunidad (sin .json)
                    return archivo.replace('.json', '')
            except Exception as e:
                print(f"❌ Error leyendo {archivo}: {e}")
                continue
    
    return None  # No se encontró la comunidad

def enviar_telegram(chat_id, mensaje):
    """
    📡 FUNCIÓN PARA ENVIAR MENSAJES SIMPLES A TELEGRAM
    
    Esta función se usa para enviar las alertas de emergencia
    Utiliza la API HTTP de Telegram directamente
    
    Args:
        chat_id (str): ID del chat/grupo donde enviar
        mensaje (str): Texto del mensaje (puede incluir HTML)
    """
    if not chat_id:
        print("❌ No se encontró chat_id de Telegram para esta comunidad.")
        return

    # URL de la API de Telegram para enviar mensajes
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Payload con los datos del mensaje
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"  # Permite usar <b>, <i>, etc. en el mensaje
    }

    try:
        # Realiza la petición POST a Telegram
        response = requests.post(url, json=payload)
        if response.ok:
            print(f"✅ Mensaje Telegram enviado al grupo {chat_id}")
        else:
            print(f"❌ Error Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar mensaje Telegram: {e}")

def enviar_mensaje_telegram(chat_id, mensaje, keyboard=None):
    """
    📡 FUNCIÓN PARA ENVIAR MENSAJES CON BOTONES A TELEGRAM
    
    Similar a enviar_telegram() pero permite incluir botones inline
    Se usa para enviar el botón de emergencia cuando alguien escribe SOS
    
    Args:
        chat_id (str): ID del chat/grupo donde enviar
        mensaje (str): Texto del mensaje
        keyboard (dict, optional): Configuración de botones inline
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    
    # Si se proporcionaron botones, los incluye
    if keyboard:
        payload["reply_markup"] = keyboard

    try:
        response = requests.post(url, json=payload)
        if response.ok:
            print(f"✅ Mensaje con botón enviado al chat {chat_id}")
        else:
            print(f"❌ Error enviando mensaje: {response.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar mensaje: {e}")

# ============================================================================
# RUTA PARA LLAMADAS DE VOZ (TWILIO)
# ============================================================================

@app.route('/twilio-voice', methods=['POST'])
def twilio_voice():
    """
    🎤 ENDPOINT PARA MANEJAR LLAMADAS TELEFÓNICAS
    
    Twilio llama a esta ruta cuando se establece una llamada
    Devuelve TwiML (XML) con instrucciones sobre qué decir
    
    Returns:
        XML: Instrucciones TwiML para Twilio
    """
    response = VoiceResponse()
    # Configura el mensaje de voz en español con voz Alice
    response.say(
        "Emergencia. Alarma vecinal. Revisa tu celular.", 
        voice='alice',      # Voz femenina de Twilio
        language='es-ES'    # Español de España (más claro)
    )
    return Response(str(response), mimetype='application/xml')

# ============================================================================
# INICIO DEL SERVIDOR
# ============================================================================

if __name__ == '__main__':
    """
    ▶️ PUNTO DE ENTRADA DEL SERVIDOR
    
    Configuración para producción:
    - host='0.0.0.0': Acepta conexiones desde cualquier IP
    - port=8000: Puerto por defecto (Railway puede cambiarlo automáticamente)
    """
    app.run(host='0.0.0.0', port=8000)

# ============================================================================
# FLUJO COMPLETO DEL SISTEMA:
# ============================================================================
# 
# 1. CONFIGURACIÓN INICIAL:
#    - Usuario agrega el bot a un grupo de Telegram
#    - Se configura el webhook para que Telegram envíe mensajes a este servidor
#    - Se crea un archivo JSON con los datos de la comunidad
# 
# 2. ACTIVACIÓN DE EMERGENCIA:
#    a. Usuario escribe "sos" en el grupo
#    b. Telegram envía el mensaje al webhook (/webhook/telegram)
#    c. El servidor identifica la comunidad y guarda el user_id
#    d. Se envía un botón "ABRIR BOTÓN DE EMERGENCIA" al grupo
# 
# 3. APERTURA DEL FORMULARIO:
#    a. Usuario presiona el botón
#    b. Se abre la página web (/) con parámetros ?comunidad=X&user_id=Y
#    c. El JavaScript carga y identifica al usuario específico
# 
# 4. ENVÍO DE ALERTA:
#    a. Usuario llena el formulario y presiona "Enviar Alerta Roja"
#    b. JavaScript envía POST a /api/alert con todos los datos
#    c. Servidor identifica al usuario, prepara el mensaje y notifica
# 
# 5. NOTIFICACIONES:
#    a. Se envía mensaje detallado al grupo de Telegram
#    b. Se realizan llamadas automáticas a todos los miembros
#    c. El sistema queda listo para la próxima emergencia
# 
# ============================================================================
