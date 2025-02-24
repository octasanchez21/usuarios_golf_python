import os
import requests
from flask import Flask, request, jsonify
from requests.auth import HTTPDigestAuth

app = Flask(__name__)

# Configuración de Hikvision
host = "192.168.1.68"  # Cambia esto por la IP de tu dispositivo Hikvision
devIndex = 1
username = "admin"
password = "12345"

# Configuración de TagoIO
tago_token = os.getenv("TAGO_TOKEN")  # Asegúrate de que este token esté en tus variables de entorno

def digest_request(url, method, data=None):
    try:
        headers = {"Content-Type": "application/json"}
        auth = HTTPDigestAuth(username, password)
        if method == "POST":
            response = requests.post(url, json=data, headers=headers, auth=auth)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers, auth=auth)
        elif method == "GET":
            response = requests.get(url, headers=headers, auth=auth)
        else:
            return None, "Método HTTP no soportado"

        return response.json(), None if response.status_code == 200 else response.text
    except Exception as e:
        return None, str(e)

def send_to_tago(variable, value, unit=None):
    url = "https://api.tago.io/data"
    headers = {
        "Content-Type": "application/json",
        "Authorization": tago_token
    }
    payload = {"variable": variable, "value": value}
    if unit:
        payload["unit"] = unit
    
    response = requests.post(url, headers=headers, json=[payload])
    return response.json() if response.status_code == 200 else {"error": response.text}

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

    tago_response = send_to_tago("nuevo_usuario", data["employeeNo"])
    return jsonify({"hikvision_response": response, "tago_response": tago_response})

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

    tago_response = send_to_tago("usuario_eliminado", employeeNo)
    return jsonify({"hikvision_response": response, "tago_response": tago_response})

@app.route('/sync', methods=['POST'])
def sync_users():
    url = f"http://{host}/ISAPI/AccessControl/UserInfo/Search?format=json"
    response, error = digest_request(url, "POST", {})
    if error:
        return jsonify({"error": error}), 500
    
    for user in response.get("UserInfoSearch", {}).get("UserInfo", []):
        send_to_tago("usuario_sincronizado", user["employeeNo"])
    
    return jsonify({"message": "Usuarios sincronizados con TagoIO"})

@app.route('/send_to_tago', methods=['POST'])
def send_custom_data():
    data = request.json
    variable = data.get("variable")
    value = data.get("value")
    unit = data.get("unit")
    
    if not variable or value is None:
        return jsonify({"error": "Faltan datos"}), 400
    
    response = send_to_tago(variable, value, unit)
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
