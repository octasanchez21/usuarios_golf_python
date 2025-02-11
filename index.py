# Tener en cuenta peticion POST para consultar usuarios MAX 30 usuarios


import os
import requests
import mimetypes
import json
from urllib import request
from tago import Analysis
from requests.auth import HTTPDigestAuth

# Configuración
host = "34.221.158.219"
devIndex = "F5487AA0-2485-4CFB-9304-835DCF118B43"
url_delete_face = f"http://{host}/ISAPI/Intelligent/FDLib/FDSearch/Delete?format=json&devIndex={devIndex}"
url_create_face = f"http://{host}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json&devIndex={devIndex}"
username = 'admin'
password = 'Inteliksa6969'

# Función para hacer peticiones con autenticación Digest
def digest_request(url, method, body=None):
    headers = {"Content-Type": "application/json"}
    auth = HTTPDigestAuth(username, password) # Clase de la libreria "requests.auth" donde implementa la autenticacion Digest, pasandole el usuario y contraseña establecido
    
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
    # Leer archivo JSON con usuarios de SAP
    try:    # "open" para abrir el archivo en modo lectura "r", para que se lea correctamente se utiliza "encoding="utf-8"".
        with open("./usuarios_sap.json", "r", encoding="utf-8") as file: # El bloque "with" garantiza cerrar el archivo automaticamente después de usarlo.
            usuarios_sap = json.load(file) # Convierte el JSON en una lista de diccionarios, cada uno representa un usuario.
        context.log(f"Usuarios SAP cargados correctamente: {len(usuarios_sap)} usuarios encontrados.") # "len" indica cuantos usuarios se cargaron.
    except (FileNotFoundError, json.JSONDecodeError) as e: # "FileNotFoundError" no existe el archivo, "json.JSONDecodeError" formato JSON no valido.
        context.log(f"Error al cargar usuarios de SAP: {e}")
        return

    # Obtener usuarios actuales de Hikvision
    hikvision_data = get_hikvision_users()
    if not hikvision_data: # Es "none", lo que significa que hubo un error
        context.log("Error al obtener usuarios de Hikvision.")
        return

    # Accede al objeto que contiene los usuarios "get("UserInfoSearch", {})"
    hikvision_users = hikvision_data.get("UserInfoSearch", {}).get("UserInfo", []) #  ".get("UserInfo", []) "para obtener la lista de usuarios.
    context.log(f"Usuarios Hikvision cargados correctamente: {len(hikvision_users)} usuarios encontrados.")

    # Crear conjuntos de employeeNo para comparar
    hikvision_employee_nos = [user["employeeNo"] for user in hikvision_users] # Crea una lista de los "employeeNo" de hikvision
    sap_employee_nos = [user["employeeNo"] for user in usuarios_sap] # Crea una lista de los "employeeNo" de SAP JSON.

    # Identificar usuarios nuevos
    # Crea una lista de usuarios cuyo "employeeNo" no esten en "hikvision_employee_nos"
    nuevos_usuarios = [user for user in usuarios_sap if user["employeeNo"] not in hikvision_employee_nos]
    for usuario in nuevos_usuarios: # Itera sobre la lista "nuevos_usuarios"
        if add_hikvision_user(usuario): # Llama la función "add_hikvision_user" para agregar cada usuario al hikvision.
            context.log(f"✅ Usuario {usuario['employeeNo']} agregado.")

    # Identificar usuarios para actualizar
    usuarios_para_actualizar = [ # Se crea una lista de usuarios que necesitan actualización
     # "usuario" elemento incluida en la nueva lista si cumple la condición
        usuario for usuario in usuarios_sap  # "for usuario in usuarios_sap" Itera sobre cada usuario en la lista.
        if any( # La función (any) verifica si al menos un elemento es "true". any(condición for elemento in iterable)
            user["employeeNo"] == usuario["employeeNo"] and ( # Verifica si el "employeeNo" de SAP coincide con el "employeeNo" de un usuario Hikvision
            # Verifica si el nombre del usuario en SAP es diferente al nombre del usuario en Hikvision. 
            # Verifica si el estado de validez (Valid["enable"]) del usuario en SAP es diferente al estado de validez en Hikvision.
                user["name"] != usuario["name"] or user["Valid"]["enable"] != usuario["valid"]["enable"]
            ) for user in hikvision_users
        )
    ]
    for usuario in usuarios_para_actualizar: # Contiene los usuario que necesitas ser actualizados
        if update_hikvision_user(usuario): # Llama la funcon para enviar la solicitud para actualizar los datos del usuario.
            context.log(f"✅ Usuario {usuario['employeeNo']} actualizado.")

    # Identificar usuarios a eliminar
    usuarios_para_eliminar = [  # Crea una lista para los usuarios que no estan en SAP
       # Filtra usuarios cuyo "employeeNo" no esta en "sap_employee_nos".
        user for user in hikvision_users if user["employeeNo"] not in sap_employee_nos
    ]
    for user in usuarios_para_eliminar: # Itera la lista de usuarios que debe eliminar
        if delete_hikvision_user(user["employeeNo"]): # Llama la funcion que elimina el usuario pasandole el "employeeNo"
            context.log(f"🗑️ Usuario {user['employeeNo']} eliminado.")

    # Procesar rostros
    for usuario in usuarios_sap: # Itera sobre los usuarios de SAP
        employee_no = usuario.get("employeeNo") # Obtiene el numero de empleado actual.
        if not employee_no: # Si el usuario no tiene "employee_no" se saltea este usuario
            continue

        # Eliminar rostro existente
        delete_payload = { # Contrucción del payload para eliminar rostro
            "FaceInfoDelCond": {
                "faceLibType": "blackFD",
                "EmployeeNoList": [{"employeeNo": employee_no}] # Solo se incluye el numero de empleado del usuario actual.
            }
        }
        try:
            response = requests.put(url_delete_face, json=delete_payload, auth=HTTPDigestAuth(username, password), timeout=10)
            if response.status_code == 200:
                context.log(f"🗑️ Rostro eliminado para empleado {employee_no}")
            else:
                context.log(f"⚠️ Error al eliminar rostro para {employee_no}: {response.text}")
        except requests.exceptions.RequestException as e:
            context.log(f"⚠️ Error en la solicitud DELETE para {employee_no}: {e}")

    # Filtrar usuarios que tienen faceURL en SAP (para subir nuevos rostros)
    usuarios_a_subir = [u for u in usuarios_sap if u.get("faceURL")] # Crea nueva lista que contiene los usuarios de SAP con "faceURL"
    context.log(f"Usuarios a subir: {len(usuarios_a_subir)}") 

    # Subir imágenes a Hikvision
    for usuario in usuarios_a_subir:
        image_url = usuario.get("faceURL") # Obtiene la URL de la imagen
        employee_no = usuario.get("employeeNo") # Obtiene el "employeeNo" del usuario
        if not image_url: # Si el usuario no tiene "URL" valida se salta este usuario.
            context.log(f"Error: El empleado {employee_no} no tiene una URL de imagen válida.")
            continue

        temp_image_path = f"{employee_no}.jpg" # Usa el "employee_no" para nombrar temporalmente el archivo que se va descargar
        context.log(f"Descargando imagen para empleado {employee_no}: {image_url}")
        try:
            # Descargar imagen
            request.urlretrieve(image_url, temp_image_path) # Descarga la imagen desde la URL y se guarda con el nombre temporal

            # Verificar que la imagen se haya guardado correctamente
            # "os.path.exists(temp_image_path)" verifica que el archivo exista
            # "os.path.getsize(temp_image_path)" verifica si el archivo tiene un tamaño mayor a cero
            if not os.path.exists(temp_image_path) or os.path.getsize(temp_image_path) == 0:
                context.log(f"Error: No se pudo descargar correctamente la imagen para {employee_no}.")
                continue

            # Leer la imagen
            with open(temp_image_path, "rb") as img_file: # Abre el archivo en modo binario "rb" y lee su contenido
                img_data = img_file.read() # Guarda los datos de la imagen en la variable "img_data"

            file_type = mimetypes.guess_type(temp_image_path)[0] or 'image/jpeg' # Determina el tipo MIME de la imagen

            # Datos de FaceInfo para Hikvision
            face_info = {
                "FaceInfo": {
                    "employeeNo": employee_no,
                    "faceLibType": "blackFD"
                }
            }

            # Enviar la imagen a Hikvision
            files = {'FaceDataRecord': ("face.jpg", img_data, file_type)}
            data = {'data': json.dumps(face_info)}
            response = requests.post(url_create_face, data=data, files=files, auth=HTTPDigestAuth(username, password), timeout=10) # ENVIO DE IMAGEN
            if response.status_code == 200:
                context.log(f"✅ Rostro agregado correctamente para {employee_no}")
            else:
                context.log(f"❌ Error al agregar rostro para {employee_no}: {response.text}")
        except Exception as e:
            context.log(f"⚠️ Error al procesar imagen para {employee_no}: {e}")
        finally:
            # Eliminar archivo temporal después de usarlo
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                context.log(f"🗑️ Archivo temporal eliminado: {temp_image_path}")

    context.log("Proceso completado.")

# Análisis principal
def my_analysis(context, scope):
    context.log('Iniciando análisis...')
    context.log('Alcance del análisis:', scope)
    sync_users(context)

# Inicializar el análisis
ANALYSIS_TOKEN = 'a-6d6726c2-f167-4610-a9e5-5a08a92b6bb3'  # Reemplaza con tu token de análisis de TagoIO
Analysis(ANALYSIS_TOKEN).init(my_analysis)