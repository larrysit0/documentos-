import os
import requests
import json
from flask import Flask, request, jsonify, render_template

print("--- DEBUG: servidor.py: INICIO DEL SCRIPT ---")

app = Flask(__name__)

# 🔐 TOKEN del bot (configurado como variable de entorno en Railway)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("--- DEBUG: ERROR: La variable de entorno TELEGRAM_BOT_TOKEN no está configurada. ---")
else:
    print("--- DEBUG: TELEGRAM_BOT_TOKEN cargado correctamente. ---")

@app.route('/')
def index():
    print("--- DEBUG: Ruta / fue accedida. Sirviendo index.html ---")
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    print("--- DEBUG: Endpoint /webhook fue accedido. ---")
    try:
        update = request.json
        print("--- DEBUG: Update de Telegram recibido:", json.dumps(update, indent=2))
        
        message = update.get('message')
        if message:
            chat_id = message['chat']['id']
            text = message.get('text', '')
            print(f"--- DEBUG: Mensaje procesado. chat_id: {chat_id}, texto: '{text}' ---")
            
            if text.startswith('/registrar') or text.startswith('/obtener_id'):
                print(f"--- DEBUG: Comando '{text}' detectado. Preparando respuesta... ---")
                
                # URL de tu web app de registro en Railway
                webapp_url = "https://alarma2-production.up.railway.app"
                
                payload = {
                    "chat_id": chat_id,
                    "text": "Presiona el botón para obtener tu ID de Telegram.",
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "Obtener mi ID",
                                    "web_app": { "url": webapp_url }
                                }
                            ]
                        ]
                    }
                }
                
                send_telegram_message(chat_id, payload)
            else:
                print(f"--- DEBUG: No se detectó un comando válido. Ignorando mensaje. ---")
        else:
            print("--- DEBUG: La actualización no contiene un mensaje de chat. ---")
    except Exception as e:
        print(f"--- DEBUG: ERROR GENERAL en el webhook: {e} ---")
    
    return jsonify({"status": "ok"}), 200

@app.route('/api/register', methods=['POST'])
def register_id():
    print("--- DEBUG: Endpoint /api/register fue accedido. ---")
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        user_info = data.get('user_info', {})
        
        if telegram_id:
            print(f"--- DEBUG: ID de Telegram recibido: {telegram_id} ---")
            print(f"--- DEBUG: Información de usuario: {user_info} ---")
            return jsonify({"status": "ID recibido y registrado."}), 200
        else:
            print("--- DEBUG: Error: No se recibió ID de Telegram. ---")
            return jsonify({"error": "ID no proporcionado"}), 400
    except Exception as e:
        print(f"--- DEBUG: ERROR GENERAL en /api/register: {e} ---")
        return jsonify({"error": "Error interno del servidor"}), 500

def send_telegram_message(chat_id, payload):
    # ✅ ESTA ES LA LÍNEA CORREGIDA
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    print(f"--- DEBUG: Intentando enviar mensaje a la URL: {url} ---")
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"--- DEBUG: Respuesta de Telegram (status code): {response.status_code} ---")
        response.raise_for_status()
        print(f"--- DEBUG: Mensaje enviado exitosamente a {chat_id} (Telegram). ---")
    except requests.exceptions.RequestException as e:
        print(f"--- DEBUG: ERROR al enviar mensaje a Telegram {chat_id}: {e} ---")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
