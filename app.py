import os
import requests
import mimetypes
import json
from urllib import request
from dotenv import load_dotenv
from tago import Analysis
from requests.auth import HTTPDigestAuth

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

# Función para eliminar rostro de Hikvision
def delete_face(employee_no, context):
    payload = {
        "FaceInfoDelCond": {
            "faceLibType": "blackFD",
            "EmployeeNoList": [{"employeeNo": employee_no}]
        }
    }
    try:
        response = requests.put(url_delete_face, json=payload, auth=HTTPDigestAuth(username, password), timeout=10)
        if response.status_code == 200:
            context.log(f"✅ Rostro eliminado para empleado {employee_no}")
        else:
            context.log(f"❌ Error eliminando rostro {employee_no}: {response.text}")
    except Exception as e:
        context.log(f"⚠️ Error en DELETE para {employee_no}: {e}")

# Función para subir rostro a Hikvision
def upload_face(employee_no, image_url, context):
    temp_image_path = f"{employee_no}.jpg"
    
    try:
        # Descargar la imagen
        request.urlretrieve(image_url, temp_image_path)

        # Verificar que la imagen existe
        if not os.path.exists(temp_image_path) or os.path.getsize(temp_image_path) == 0:
            context.log(f"❌ Error: No se pudo descargar correctamente la imagen para {employee_no}")
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

        # Enviar la imagen a Hikvision
        files = {'FaceDataRecord': ("face.jpg", img_data, file_type)}
        data = {'data': json.dumps(face_info)}
        response = requests.post(url_create_face, data=data, files=files, auth=HTTPDigestAuth(username, password), timeout=10)

        if response.status_code == 200:
            context.log(f"✅ Rostro agregado correctamente para {employee_no}")
        else:
            context.log(f"❌ Error al agregar rostro para {employee_no}: {response.text}")
    except Exception as e:
        context.log(f"⚠️ Error procesando imagen para {employee_no}: {e}")
    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
            context.log(f"🗑️ Archivo temporal eliminado: {temp_image_path}")

# Función principal para sincronizar usuarios
def sync_users(context):
    context.log("🔄 Iniciando sincronización de usuarios...")

    # Petición a Hikvision para obtener usuarios
    try:
        response = requests.post(url_sync_users, auth=HTTPDigestAuth(username, password), timeout=10)
        users = response.json().get("UserInfoSearch", {}).get("UserInfo", [])
    except Exception as e:
        context.log(f"⚠️ Error obteniendo usuarios: {e}")
        return
    
    if not users:
        context.log("⚠️ No se encontraron usuarios en Hikvision")
        return

    for user in users:
        employee_no = user.get("employeeNo")
        if not employee_no:
            continue
        
        # Aquí puedes obtener la imagen de TagoIO o SAP (depende de cómo manejes imágenes)
        image_url = f"https://mi-servidor.com/imagenes/{employee_no}.jpg"  # Ejemplo

        # Eliminar rostro existente y subir nueva imagen
        delete_face(employee_no, context)
        upload_face(employee_no, image_url, context)

    context.log("✅ Sincronización completada.")

# Función que inicia el análisis de TagoIO
def my_analysis(context, scope):
    context.log("🔍 Iniciando análisis...")
    sync_users(context)

# Token de TagoIO Analysis
Analysis(ANALYSIS_TOKEN).init(my_analysis)
