import os
import json
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from requests.auth import HTTPDigestAuth

# Cargar variables de entorno
load_dotenv()

# Configuración
host = os.getenv("HOST")
devIndex = os.getenv("DEV_INDEX")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

app = Flask(__name__)

# Función para hacer peticiones con autenticación Digest
def digest_request(url, method, body=None):
    headers = {"Content-Type": "application/json"}
    auth = HTTPDigestAuth(username, password)

    if method == 'POST':
        response = requests.post(url, headers=headers, auth=auth, json=body)
    elif method == 'PUT':
        response = requests.put(url, headers=headers, auth=auth, json=body)

    if response.status_code != 200:
        return None, f"Error {response.status_code}: {response.text}"

    return response.json(), None

# Obtener usuarios de Hikvision
@app.route('/usuarios', methods=['GET'])
def get_hikvision_users():
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Search?format=json&devIndex={devIndex}"
    body = {
        "UserInfoSearchCond": {
            "searchID": "0",
            "searchResultPosition": 0,
            "maxResults": 400
        }
    }
    response, error = digest_request(url, "POST", body)
    if error:
        return jsonify({"error": error}), 500
    return jsonify(response)

# Agregar usuario en Hikvision
@app.route('/usuarios', methods=['POST'])
def add_hikvision_user():
    data = request.json
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Record?format=json&devIndex={devIndex}"
    body = {
        "UserInfo": [{
            "employeeNo": data["employeeNo"],
            "name": data["name"],
            "userType": "normal",
            "gender": "male",
            "localUIRight": False,
            "Valid": {
                "enable": data["valid"]["enable"],
                "beginTime": "2023-09-26T00:00:00",
                "endTime": "2037-12-31T23:59:59",
                "timeType": "local"
            },
            "doorRight": "1",
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "userVerifyMode": "",
            "password": data["pin"]
        }]
    }
    response, error = digest_request(url, "POST", body)
    if error:
        return jsonify({"error": error}), 500
    return jsonify(response)

# Modificar usuario en Hikvision
@app.route('/usuarios/<string:employeeNo>', methods=['PUT'])
def update_hikvision_user(employeeNo):
    data = request.json
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Modify?format=json&devIndex={devIndex}"
    body = {
        "UserInfo": {
            "employeeNo": employeeNo,
            "name": data["name"],
            "Valid": {"enable": data["valid"]["enable"]},
            "password": data["pin"]
        }
    }
    response, error = digest_request(url, "PUT", body)
    if error:
        return jsonify({"error": error}), 500
    return jsonify(response)

# Eliminar usuario en Hikvision
@app.route('/usuarios/<string:employeeNo>', methods=['DELETE'])
def delete_hikvision_user(employeeNo):
    url = f"http://{host}/ISAPI/AccessControl/UserInfoDetail/Delete?format=json&devIndex={devIndex}"
    body = {
        "UserInfoDetail": {
            "mode": "byEmployeeNo",
            "EmployeeNoList": [{"employeeNo": employeeNo}]
        }
    }
    response, error = digest_request(url, "PUT", body)
    if error:
        return jsonify({"error": error}), 500
    return jsonify(response)

# Sincronización de usuarios
@app.route('/sync', methods=['POST'])
def sync_users():
    try:
        with open("./usuarios_sap.json", "r", encoding="utf-8") as file:
            usuarios_sap = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return jsonify({"error": f"Error al cargar usuarios de SAP: {str(e)}"}), 500

    # Obtener usuarios actuales de Hikvision
    hikvision_data, error = get_hikvision_users()
    if error:
        return jsonify({"error": "Error al obtener usuarios de Hikvision"}), 500

    hikvision_users = hikvision_data.get("UserInfoSearch", {}).get("UserInfo", [])
    hikvision_employee_nos = [user["employeeNo"] for user in hikvision_users]
    sap_employee_nos = [user["employeeNo"] for user in usuarios_sap]

    resultados = {"nuevos": [], "actualizados": [], "eliminados": []}

    # Identificar usuarios nuevos
    nuevos_usuarios = [user for user in usuarios_sap if user["employeeNo"] not in hikvision_employee_nos]
    for usuario in nuevos_usuarios:
        response, error = digest_request(
            f"http://{host}/ISAPI/AccessControl/UserInfo/Record?format=json&devIndex={devIndex}",
            "POST",
            {"UserInfo": [usuario]},
        )
        if response:
            resultados["nuevos"].append(usuario["employeeNo"])

    # Identificar usuarios para actualizar
    usuarios_para_actualizar = [
        usuario for usuario in usuarios_sap if any(
            user["employeeNo"] == usuario["employeeNo"] and (
                user["name"] != usuario["name"] or user["Valid"]["enable"] != usuario["valid"]["enable"]
            ) for user in hikvision_users
        )
    ]
    for usuario in usuarios_para_actualizar:
        response, error = digest_request(
            f"http://{host}/ISAPI/AccessControl/UserInfo/Modify?format=json&devIndex={devIndex}",
            "PUT",
            {"UserInfo": usuario},
        )
        if response:
            resultados["actualizados"].append(usuario["employeeNo"])

    # Identificar usuarios a eliminar
    usuarios_para_eliminar = [user for user in hikvision_users if user["employeeNo"] not in sap_employee_nos]
    for user in usuarios_para_eliminar:
        response, error = digest_request(
            f"http://{host}/ISAPI/AccessControl/UserInfoDetail/Delete?format=json&devIndex={devIndex}",
            "PUT",
            {"UserInfoDetail": {"mode": "byEmployeeNo", "EmployeeNoList": [{"employeeNo": user["employeeNo"]}]}},
        )
        if response:
            resultados["eliminados"].append(user["employeeNo"])

    return jsonify(resultados)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
