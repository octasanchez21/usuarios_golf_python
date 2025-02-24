import os
import requests
import json
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from tago import Analysis
from requests.auth import HTTPDigestAuth


# Cargar variables de entorno
load_dotenv()

host = os.getenv("HOST")
devIndex = os.getenv("DEV_INDEX")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
ANALYSIS_TOKEN = os.getenv("ANALYSIS_TOKEN")

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello, Render!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Usa el puerto de Render
    app.run(host='0.0.0.0', port=port)

# Función para hacer peticiones con autenticación Digest
def digest_request(url, method, body=None):
    headers = {"Content-Type": "application/json"}
    auth = HTTPDigestAuth(username, password)
    
    if method == 'POST':
        response = requests.post(url, headers=headers, auth=auth, json=body)
    elif method == 'PUT':
        response = requests.put(url, headers=headers, auth=auth, json=body)
    
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None
    
    return response.json()

# Obtener usuarios de Hikvision
def get_hikvision_users():
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Search?format=json&devIndex={devIndex}"
    body = {
        "UserInfoSearchCond": {
            "searchID": "0",
            "searchResultPosition": 0,
            "maxResults": 400
        }
    }
    return digest_request(url, "POST", body)

# Agregar usuario en Hikvision
def add_hikvision_user(usuario):
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Record?format=json&devIndex={devIndex}"
    body = {
        "UserInfo": [{
            "employeeNo": usuario["employeeNo"],
            "name": usuario["name"],
            "userType": "normal",
            "gender": "male",
            "localUIRight": False,
            "Valid": {
                "enable": usuario["valid"]["enable"],
                "beginTime": "2023-09-26T00:00:00",
                "endTime": "2037-12-31T23:59:59",
                "timeType": "local"
            },
            "doorRight": "1",
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "userVerifyMode": "",
            "password": usuario["pin"]
        }]
    }
    return digest_request(url, "POST", body)

# Modificar usuario en Hikvision
def update_hikvision_user(usuario):
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Modify?format=json&devIndex={devIndex}"
    body = {
        "UserInfo": {
            "employeeNo": usuario["employeeNo"],
            "name": usuario["name"],
            "Valid": {"enable": usuario["valid"]["enable"]},
            "password": usuario["pin"]
        }
    }
    return digest_request(url, "PUT", body)

# Eliminar usuario en Hikvision
def delete_hikvision_user(employeeNo):
    url = f"http://{host}/ISAPI/AccessControl/UserInfoDetail/Delete?format=json&devIndex={devIndex}"
    body = {
        "UserInfoDetail": {
            "mode": "byEmployeeNo",
            "EmployeeNoList": [{"employeeNo": employeeNo}]
        }
    }
    return digest_request(url, "PUT", body)

# Sincronización de usuarios
def sync_users(context):
    try:
        with open("./usuarios_sap.json", "r", encoding="utf-8") as file:
            usuarios_sap = json.load(file)
        context.log(f"Usuarios SAP cargados correctamente: {len(usuarios_sap)} usuarios encontrados.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        context.log(f"Error al cargar usuarios de SAP: {e}")
        return

    hikvision_data = get_hikvision_users()
    if not hikvision_data:
        context.log("Error al obtener usuarios de Hikvision.")
        return

    hikvision_users = hikvision_data.get("UserInfoSearch", {}).get("UserInfo", [])
    context.log(f"Usuarios Hikvision cargados correctamente: {len(hikvision_users)} usuarios encontrados.")

    hikvision_employee_nos = [user["employeeNo"] for user in hikvision_users]
    sap_employee_nos = [user["employeeNo"] for user in usuarios_sap]

    nuevos_usuarios = [user for user in usuarios_sap if user["employeeNo"] not in hikvision_employee_nos]
    for usuario in nuevos_usuarios:
        if add_hikvision_user(usuario):
            context.log(f"✅ Usuario {usuario['employeeNo']} agregado.")

    usuarios_para_actualizar = [
        usuario for usuario in usuarios_sap
        if any(
            user["employeeNo"] == usuario["employeeNo"] and (
                user["name"] != usuario["name"] or user["Valid"]["enable"] != usuario["valid"]["enable"]
            ) for user in hikvision_users
        )
    ]
    for usuario in usuarios_para_actualizar:
        if update_hikvision_user(usuario):
            context.log(f"✅ Usuario {usuario['employeeNo']} actualizado.")

    usuarios_para_eliminar = [user for user in hikvision_users if user["employeeNo"] not in sap_employee_nos]
    for user in usuarios_para_eliminar:
        if delete_hikvision_user(user["employeeNo"]):
            context.log(f"🗑️ Usuario {user['employeeNo']} eliminado.")

    context.log("Proceso completado.")

# Análisis principal
def my_analysis(context, scope):
    context.log('Iniciando análisis...')
    context.log('Alcance del análisis:', scope)
    sync_users(context)

# Inicializar el análisis
ANALYSIS_TOKEN = 'a-6d6726c2-f167-4610-a9e5-5a08a92b6bb3'
Analysis(ANALYSIS_TOKEN).init(my_analysis)

