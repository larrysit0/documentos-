# ===============================================================================
# 🚨 SISTEMA DE EMERGENCIA VECINAL - SERVIDOR PRINCIPAL
# ===============================================================================
# Este archivo maneja todas las operaciones del backend:
# - Recepción de alertas de emergencia
# - Envío de mensajes a Telegram
# - Llamadas telefónicas automáticas con Twilio
# - Gestión de comunidades y usuarios
# ===============================================================================

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from datetime import datetime
import os
import json
import requests

# 📦 Twilio para llamadas telefónicas automáticas
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

# ===============================================================================
# 🔧 CONFIGURACIÓN INICIAL DEL SERVIDOR
# ===============================================================================

app = Flask(__name__)  # Crear la aplicación Flask
CORS(app)  # Permitir peticiones desde otros dominios (cross-origin)

# 📁 Ruta donde están almacenados los archivos JSON de cada comunidad
DATA_FILE = os.path.join(os.path.dirname(__file__), 'comunidades')

# 🔑 Variables de entorno para credenciales de Twilio (llamadas)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')    # ID de cuenta Twilio
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')      # Token de autenticación
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')    # Número desde el cual se hacen llamadas

# 🤖 Token del bot de Telegram para enviar mensajes
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 🌐 URL base del servidor (se usa para generar enlaces del botón de emergencia)
BASE_URL = os.getenv('BASE_URL', 'https://tu-servidor.com')

# 🎯 Cliente Twilio inicializado para hacer llamadas
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# 📝 Diccionario temporal para recordar qué usuario activó SOS en cada comunidad
# Formato: {"nombre_comunidad": "telegram_user_id"}
usuarios_sos_activos = {}

# ===============================================================================
# 🌐 RUTAS WEB - PÁGINAS Y APIs
# ===============================================================================

@app.route('/')
def index():
    """
    📄 Página principal del sistema de emergencia
    Renderiza el HTML donde está el botón de emergencia
    """
    return render_template('index.html')

@app.route('/api/comunidades')
def listar_comunidades():
    """
    📋 API para obtener lista de todas las comunidades disponibles
    Lee la carpeta 'comunidades' y devuelve nombres de archivos JSON
    """
    comunidades = []
    if os.path.exists(DATA_FILE):  # Verificar que la carpeta existe
        for archivo in os.listdir(DATA_FILE):  # Recorrer todos los archivos
            if archivo.endswith('.json'):  # Solo archivos JSON
                # Quitar la extensión .json del nombre
                comunidades.append(archivo.replace('.json', ''))
    return jsonify(comunidades)  # Devolver como JSON

@app.route('/api/ubicaciones/<comunidad>')
def ubicaciones_de_comunidad(comunidad):
    """
    📍 API para obtener miembros de una comunidad específica
    Parámetro: nombre de la comunidad (ej: "villa", "sanjuan")
    Retorna: lista de miembros con sus datos (nombre, teléfono, dirección, etc.)
    """
    # Construir ruta al archivo JSON de la comunidad
    path = os.path.join(DATA_FILE, f"{comunidad}.json")
    
    # Verificar que el archivo existe
    if not os.path.exists(path):
        return jsonify({"error": "Comunidad no encontrada"}), 404
    
    # Leer el archivo JSON
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Si el JSON tiene estructura {"miembros": [...]} extraer solo miembros
    if isinstance(data, dict):
        return jsonify(data.get("miembros", []))
    else:
        # Si es directamente una lista, devolverla tal como está
        return jsonify(data)

# ===============================================================================
# 🚨 FUNCIÓN PRINCIPAL - PROCESAR ALERTA DE EMERGENCIA
# ===============================================================================

@app.route('/api/alert', methods=['POST'])
def recibir_alerta():
    """
    🚨 FUNCIÓN PRINCIPAL: Procesa una alerta de emergencia
    
    Flujo:
    1. Recibe datos del botón de emergencia (descripción, ubicación, comunidad)
    2. Identifica quién envió la alerta
    3. Envía mensaje a grupo de Telegram
    4. Llama por teléfono a TODOS los miembros EXCEPTO al que reportó
    
    ⭐ CARACTERÍSTICA PRINCIPAL: No llama al reportante para mantener discreción
    """
    
    # 📦 Obtener datos enviados desde el frontend
    data = request.get_json()
    print("📦 Datos recibidos:", data)

    # 🔍 Extraer información específica del payload
    tipo = data.get('tipo')                    # Tipo de alerta
    descripcion = data.get('descripcion')      # Descripción de la emergencia
    ubicacion = data.get('ubicacion', {})      # Coordenadas lat/lon
    direccion = data.get('direccion')          # Dirección en texto
    comunidad = data.get('comunidad')          # Nombre de la comunidad
    telegram_user_id = data.get('telegram_user_id')  # 🎯 ID del usuario que reporta

    lat = ubicacion.get('lat')  # Latitud
    lon = ubicacion.get('lon')  # Longitud

    # ✅ Validación: verificar que tenemos los datos mínimos necesarios
    if not descripcion or not lat or not lon or not comunidad:
        return jsonify({'error': 'Faltan datos'}), 400

    # 📂 Cargar archivo JSON de la comunidad
    archivo_comunidad = os.path.join(DATA_FILE, f"{comunidad}.json")
    if not os.path.exists(archivo_comunidad):
        return jsonify({'error': 'Comunidad no encontrada'}), 404

    with open(archivo_comunidad, 'r', encoding='utf-8') as f:
        datos_comunidad = json.load(f)

    # 📋 Extraer lista de miembros y chat_id de Telegram
    miembros = datos_comunidad.get('miembros', [])
    telegram_chat_id = datos_comunidad.get('telegram_chat_id')

    # ===============================================================================
    # 🎯 IDENTIFICACIÓN DEL USUARIO QUE REPORTA LA EMERGENCIA
    # ===============================================================================
    
    miembro_reportante = None
    
    # 🥇 PRIORIDAD 1: Si tenemos telegram_user_id en la URL, buscar por ese ID
    if telegram_user_id:
        for miembro in miembros:
            # Comparar IDs como strings para evitar problemas de tipos
            if str(miembro.get('telegram_id')) == str(telegram_user_id):
                miembro_reportante = miembro
                print(f"👤 Usuario encontrado por Telegram ID: {miembro['nombre']}")
                break
    
    # 🥈 PRIORIDAD 2: Si no hay telegram_user_id, buscar en usuarios_sos_activos
    # (esto pasa cuando alguien escribió "sos" pero no se pasó el ID en la URL)
    if not miembro_reportante and comunidad in usuarios_sos_activos:
        user_id_sos = usuarios_sos_activos[comunidad]
        for miembro in miembros:
            if str(miembro.get('telegram_id')) == str(user_id_sos):
                miembro_reportante = miembro
                print(f"👤 Usuario encontrado por SOS activo: {miembro['nombre']}")
                # Limpiar el registro después de usar
                del usuarios_sos_activos[comunidad]
                break
    
    # 🥉 FALLBACK: Si no encontramos al usuario específico, usar el primer miembro
    if not miembro_reportante and miembros:
        miembro_reportante = miembros[0]
        print("⚠️ No se pudo identificar al usuario específico, usando el primer miembro como fallback")
    
    # 📝 Preparar información del reportante para el mensaje
    if miembro_reportante:
        nombre_reportante = miembro_reportante.get('nombre', 'Usuario desconocido')
        direccion_reportante = miembro_reportante.get('direccion', direccion or 'Dirección no disponible')
        
        # 🗺️ Decidir qué coordenadas usar:
        # Si están usando ubicación en tiempo real, mantener lat/lon recibidos
        # Si no, usar la ubicación predeterminada del miembro del JSON
        if not data.get('ubicacion_tiempo_real', False):
            geo_miembro = miembro_reportante.get('geolocalizacion', {})
            if geo_miembro:
                lat = geo_miembro.get('lat', lat)
                lon = geo_miembro.get('lon', lon)
    else:
        # Si no se encontró ningún miembro, usar datos genéricos
        nombre_reportante = 'Usuario desconocido'
        direccion_reportante = direccion or 'Dirección no disponible'

    # ===============================================================================
    # 📱 ENVÍO DE MENSAJE A TELEGRAM
    # ===============================================================================
    
    # 📝 Construir mensaje formateado para Telegram
    mensaje = f"""
🚨 <b>ALERTA VECINAL</b> 🚨

<b>Comunidad:</b> {comunidad.upper()}
<b>👤 Reportado por:</b> {nombre_reportante}
<b>📍 Dirección:</b> {direccion_reportante}
<b>📝 Descripción:</b> {descripcion}
<b>📍 Ubicación:</b> https://maps.google.com/maps?q={lat},{lon}
<b>🕐 Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""

    # 📤 Enviar mensaje al grupo de Telegram de la comunidad
    enviar_telegram(telegram_chat_id, mensaje)

    # ===============================================================================
    # 📞 LLAMADAS TELEFÓNICAS AUTOMÁTICAS (EXCLUYENDO AL REPORTANTE)
    # ===============================================================================
    
    # 🎯 NUEVA LÓGICA: Llamar a todos los miembros EXCEPTO al que activó la alarma
    telegram_id_reportante = None
    
    # Determinar el telegram_id del usuario que reporta
    if telegram_user_id:
        telegram_id_reportante = str(telegram_user_id)
    elif comunidad in usuarios_sos_activos:
        telegram_id_reportante = str(usuarios_sos_activos[comunidad])
    
    print(f"🚫 No se llamará al usuario con Telegram ID: {telegram_id_reportante}")
    
    # 📊 Contadores para estadísticas
    llamadas_realizadas = 0
    llamadas_omitidas = 0
    
    # 🔄 Iterar por todos los miembros de la comunidad
    for miembro in miembros:
        telefono = miembro.get('telefono')
        telegram_id_miembro = str(miembro.get('telegram_id', ''))
        
        # ⏭️ Saltar si no tiene número de teléfono
        if not telefono:
            continue
            
        # 🚫 FILTRO PRINCIPAL: Omitir llamada si es el usuario que reportó
        if telegram_id_reportante and telegram_id_miembro == telegram_id_reportante:
            print(f"🚫 Omitiendo llamada al reportante: {miembro.get('nombre')} ({telefono})")
            llamadas_omitidas += 1
            continue  # Pasar al siguiente miembro
            
        # 📞 Realizar llamada automática usando Twilio
        try:
            client.calls.create(
                # 🎙️ Mensaje de voz en español que se reproduce al contestar
                twiml='<Response><Say voice="alice" language="es-ES">Emergencia. Alarma vecinal. Revisa tu celular.</Say></Response>',
                from_=TWILIO_FROM_NUMBER,  # Número desde el cual se llama
                to=telefono                # Número destino
            )
            print(f"📞 Llamada iniciada a {miembro.get('nombre')}: {telefono}")
            llamadas_realizadas += 1
        except Exception as e:
            # 🚨 Manejar errores en llamadas (número inválido, saldo insuficiente, etc.)
            print(f"❌ Error al llamar a {telefono}: {e}")

    # 📊 Mostrar resumen de llamadas realizadas
    print(f"📊 Resumen de llamadas: {llamadas_realizadas} realizadas, {llamadas_omitidas} omitidas")

    # ✅ Responder al frontend que la alerta se procesó correctamente
    return jsonify({'status': f'Alerta enviada a la comunidad {comunidad}'}), 200

# ===============================================================================
# 🤖 WEBHOOK DE TELEGRAM - MANEJO DE COMANDOS
# ===============================================================================

@app.route('/webhook/telegram', methods=['POST'])
def webhook_telegram():
    """
    🤖 Webhook que recibe mensajes desde Telegram
    
    Comandos que maneja:
    - "sos" → Genera botón de emergencia
    - "miregistro2222" → Registra usuario en logs
    """
    try:
        # 📨 Recibir datos del webhook de Telegram
        data = request.get_json()
        print("📨 Webhook recibido:", data)
        
        # ✅ Verificar que es un mensaje (no una edición u otro evento)
        if 'message' not in data:
            return jsonify({'status': 'ok'})
        
        # 📝 Extraer información del mensaje
        message = data['message']
        chat_id = message['chat']['id']           # ID del chat/grupo
        text = message.get('text', '').strip().lower()  # Texto del mensaje en minúsculas
        
        # 👤 Información del usuario que envió el mensaje
        user = message.get('from', {})
        user_id = user.get('id')                  # ID único del usuario
        first_name = user.get('first_name', 'Sin nombre')
        username = user.get('username', 'Sin username')
        
        # ===============================================================================
        # 🚨 COMANDO "SOS" - ACTIVAR BOTÓN DE EMERGENCIA
        # ===============================================================================
        
        if text == 'sos':
            # 🔍 Buscar a qué comunidad pertenece este chat
            comunidad = obtener_comunidad_por_chat_id(chat_id)
            
            if not comunidad:
                enviar_mensaje_telegram(chat_id, "❌ Este chat no está registrado en ninguna comunidad.")
                return jsonify({'status': 'ok'})
            
            # 🎯 GUARDAR el user_id que activó SOS para poder identificarlo después
            usuarios_sos_activos[comunidad] = user_id
            print(f"👤 SOS activado por usuario {first_name} (ID: {user_id}) en comunidad {comunidad}")
            
            # 🔗 Crear URL del botón de emergencia incluyendo comunidad y user_id
            webapp_url = f"{BASE_URL}?comunidad={comunidad}&user_id={user_id}"
            
            # ⌨️ Crear teclado inline con botón que abre la web app
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🚨 ABRIR BOTÓN DE EMERGENCIA 🚨",
                        "url": webapp_url  # Al tocar este botón abre la web app
                    }
                ]]
            }
            
            mensaje_respuesta = "🚨"  # Mensaje simple que acompaña al botón
            
            # 📤 Enviar mensaje con el botón
            enviar_mensaje_telegram(chat_id, mensaje_respuesta, keyboard)
        
        # ===============================================================================
        # 📋 COMANDO "MIREGISTRO2222" - REGISTRAR USUARIO
        # ===============================================================================
        
        elif text == 'miregistro2222':
            # 📝 Registrar información del usuario en logs (para debugging)
            print(f"👤 REGISTRO: Usuario '{first_name}' (@{username}) - ID: {user_id} - Chat: {message.get('chat', {}).get('title', 'Chat privado')} ({chat_id})")
            
            # 🎨 Mensaje de confirmación visual bonito
            mensaje_registro = """  ┏━━━━━━━━━━━━━━━━━━━┓
  ┃  👐 REGISTRADO 👐  ┃
  ┗━━━━━━━━━━━━━━━━━━━┛
  🦾 Bienvenido al sistema 🦾"""
            
            # 📤 Enviar confirmación
            enviar_mensaje_telegram(chat_id, mensaje_registro)
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        # 🚨 Manejar cualquier error en el webhook
        print(f"❌ Error en webhook: {e}")
        return jsonify({'status': 'error'}), 500

# ===============================================================================
# 🔍 FUNCIONES AUXILIARES
# ===============================================================================

def obtener_comunidad_por_chat_id(chat_id):
    """
    🔍 Busca qué comunidad corresponde a un chat_id de Telegram
    
    Recorre todos los archivos JSON en la carpeta 'comunidades'
    y busca cuál tiene el telegram_chat_id que coincide
    
    Parámetro: chat_id (ID del grupo de Telegram)
    Retorna: nombre de la comunidad o None si no se encuentra
    """
    if not os.path.exists(DATA_FILE):
        return None
    
    # 🔄 Recorrer todos los archivos JSON de comunidades
    for archivo in os.listdir(DATA_FILE):
        if archivo.endswith('.json'):
            path = os.path.join(DATA_FILE, archivo)
            try:
                # 📖 Leer archivo JSON
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # ✅ Verificar si el chat_id coincide
                if data.get('telegram_chat_id') == str(chat_id):
                    # Retornar nombre de comunidad (nombre del archivo sin .json)
                    return archivo.replace('.json', '')
            except Exception as e:
                print(f"❌ Error leyendo {archivo}: {e}")
                continue
    
    return None  # No se encontró la comunidad

# ===============================================================================
# 📡 FUNCIONES DE TELEGRAM
# ===============================================================================

def enviar_telegram(chat_id, mensaje):
    """
    📡 Envía un mensaje simple a un grupo de Telegram
    
    Parámetros:
    - chat_id: ID del grupo donde enviar
    - mensaje: texto a enviar (soporta HTML)
    """
    if not chat_id:
        print("❌ No se encontró chat_id de Telegram para esta comunidad.")
        return

    # 🌐 URL de la API de Telegram para enviar mensajes
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # 📦 Payload con los datos del mensaje
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"  # Permite usar etiquetas HTML como <b>, <i>
    }

    try:
        # 📤 Hacer petición POST a la API de Telegram
        response = requests.post(url, json=payload)
        if response.ok:
            print(f"✅ Mensaje Telegram enviado al grupo {chat_id}")
        else:
            print(f"❌ Error Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Excepción al enviar mensaje Telegram: {e}")

def enviar_mensaje_telegram(chat_id, mensaje, keyboard=None):
    """
    📡 Envía un mensaje a Telegram con teclado inline opcional
    
    Parámetros:
    - chat_id: ID del grupo
    - mensaje: texto del mensaje
    - keyboard: (opcional) teclado con botones
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    
    # ⌨️ Agregar teclado si se proporcionó
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

# ===============================================================================
# 🎤 TWILIO - MANEJO DE LLAMADAS
# ===============================================================================

@app.route('/twilio-voice', methods=['POST'])
def twilio_voice():
    """
    🎤 Endpoint que define qué se dice en las llamadas automáticas
    
    Twilio llama a esta URL cuando alguien contesta el teléfono
    para saber qué mensaje reproducir
    """
    response = VoiceResponse()
    # 🗣️ Mensaje que se reproduce cuando contestan la llamada
    response.say("Emergencia. Alarma vecinal. Revisa tu celular.", voice='alice', language='es-ES')
    return Response(str(response), mimetype='application/xml')

# ===============================================================================
# ▶️ INICIO DEL SERVIDOR
# ===============================================================================

if __name__ == '__main__':
    """
    🚀 Punto de entrada del servidor
    Ejecuta la aplicación Flask en el puerto 8000
    """
    app.run(host='0.0.0.0', port=8000)
