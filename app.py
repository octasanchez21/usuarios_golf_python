import os
import requests
import mimetypes
import json
from urllib import request
from dotenv import load_dotenv
from tago import Analysis
from requests.auth import HTTPDigestAuth
from flask import Flask
import threading

# Cargar variables desde el archivo .env
load_dotenv()

# Configuración de Hikvision
host = os.getenv("HOST")
devIndex = os.getenv("DEV_INDEX")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
ANALYSIS_TOKEN = os.getenv("ANALYSIS_TOKEN")

# URLs de Hikvision
url_delete_face = f"http://{host}/ISAPI/Intelligent/FDLib/FDSearch/Delete?format=json&devIndex={devIndex}"
url_create_face = f"http://{host}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json&devIndex={devIndex}"
url_sync_users = f"http://{host}/ISAPI/AccessControl/UserInfo/Search?format=json"

# Iniciar servidor Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Servidor en ejecución"

def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Función para eliminar rostro de Hikvision
def delete_face(employee_no, context=None):
    payload = {
        "FaceInfoDelCond": {
            "faceLibType": "blackFD",
            "EmployeeNoList": [{"employeeNo": employee_no}]
        }
    }
    try:
        response = requests.put(url_delete_face, json=payload, auth=HTTPDigestAuth(username, password), timeout=10)
        message = f"✅ Rostro eliminado para empleado {employee_no}" if response.status_code == 200 else f"❌ Error eliminando rostro {employee_no}: {response.text}"
        (context.log if context else print)(message)
    except Exception as e:
        (context.log if context else print)(f"⚠️ Error en DELETE para {employee_no}: {e}")

# Función para subir rostro a Hikvision
def upload_face(employee_no, image_url, context=None):
    temp_image_path = f"{employee_no}.jpg"
    
    try:
        request.urlretrieve(image_url, temp_image_path)

        if not os.path.exists(temp_image_path) or os.path.getsize(temp_image_path) == 0:
            (context.log if context else print)(f"❌ Error: No se pudo descargar correctamente la imagen para {employee_no}")
            return
        
        with open(temp_image_path, "rb") as img_file:
            img_data = img_file.read()

        file_type = mimetypes.guess_type(temp_image_path)[0] or 'image/jpeg'

        face_info = {
            "FaceInfo": {
                "employeeNo": employee_no,
                "faceLibType": "blackFD"
            }
        }

        files = {'FaceDataRecord': ("face.jpg", img_data, file_type)}
        data = {'data': json.dumps(face_info)}
        response = requests.post(url_create_face, data=data, files=files, auth=HTTPDigestAuth(username, password), timeout=10)

        message = f"✅ Rostro agregado correctamente para {employee_no}" if response.status_code == 200 else f"❌ Error al agregar rostro para {employee_no}: {response.text}"
        (context.log if context else print)(message)
    except Exception as e:
        (context.log if context else print)(f"⚠️ Error procesando imagen para {employee_no}: {e}")
    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
            (context.log if context else print)(f"🗑️ Archivo temporal eliminado: {temp_image_path}")

# Función principal para sincronizar usuarios
def sync_users(context=None):
    (context.log if context else print)("🔄 Iniciando sincronización de usuarios...")

    try:
        response = requests.post(url_sync_users, auth=HTTPDigestAuth(username, password), timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        users = response.json().get("UserInfoSearch", {}).get("UserInfo", [])
    except Exception as e:
        (context.log if context else print)(f"⚠️ Error obteniendo usuarios: {e}")
        return
    
    if not users:
        (context.log if context else print)("⚠️ No se encontraron usuarios en Hikvision")
        return

    for user in users:
        employee_no = user.get("employeeNo")
        if not employee_no:
            continue
        
        image_url = f"https://mi-servidor.com/imagenes/{employee_no}.jpg"  # Ejemplo

        delete_face(employee_no, context)
        upload_face(employee_no, image_url, context)

    (context.log if context else print)("✅ Sincronización completada.")

# Función que inicia el análisis de TagoIO
def my_analysis(context, scope):
    (context.log if context else print)("🔍 Iniciando análisis...")
    sync_users(context)

# Iniciar TagoIO Analysis
if ANALYSIS_TOKEN:
    Analysis(ANALYSIS_TOKEN).init(my_analysis)

# Ejecutar Flask en un hilo separado
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
