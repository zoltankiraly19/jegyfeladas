from flask import Flask, jsonify, request
from flask_cors import CORS
import ibm_boto3
from ibm_botocore.config import Config
import requests
import json

app = Flask(__name__)
CORS(app)

# IBM COS konfiguráció
cos = ibm_boto3.client(
    's3',
    ibm_api_key_id=''5o6X835azJMALPLiebgIUUqRQ8e-NEM_PkQJ4thH9aI7',
    ibm_service_instance_id='f39973c6-786a-459c-9564-40f6d8e6a6b7'',
    config=Config(signature_version='oauth'),
    endpoint_url='https://s3.us-south.cloud-object-storage.appdomain.cloud'
)

bucket_name = 'servicenow3'

def load_data_from_cos(bucket_name, file_key):
    """Betölti az adatokat a COS-ból a megadott fájlnév alapján."""
    try:
        response = cos.get_object(Bucket=bucket_name, Key=file_key)
        content = response['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        print(f"Error loading {file_key}: {e}")
        return None

# Betöltjük a globális assignment groupokat és prioritásokat
assignment_groups_data = load_data_from_cos(bucket_name, 'global_assignment_groups')
if assignment_groups_data:
    assignment_groups = json.loads(assignment_groups_data)
    DROPDOWN_OPTIONS = {
        "labels": [group["name"] for group in assignment_groups],
        "values": {group["name"]: group["sys_id"] for group in assignment_groups}
    }
else:
    print("Hiba: nem sikerült betölteni az assignment groupokat a COS-ból.")
    DROPDOWN_OPTIONS = {"labels": [], "values": {}}

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    """Jegy létrehozása felhasználói kiválasztás alapján."""
    data = request.json
    user_name = data.get('felhasználónév')
    selected_option = data.get('csoport')
    selected_priority = data.get('prioritás')
    short_description = data.get('leírás')

    # Betöltjük a felhasználó tokenjét és sys_id-jét a COS-ból
    user_token = load_data_from_cos(bucket_name, f"{user_name}_user_token")
    user_sys_id = load_data_from_cos(bucket_name, f"{user_name}_user_sys_id")

    if not user_token or not user_sys_id:
        return jsonify({
            "ServiceNow": "A megadott felhasználónévhez nem található a token vagy sys_id."
        }), 400

    # Ellenőrizzük, hogy az assignment group kiválasztása érvényes-e
    assignment_group_id = DROPDOWN_OPTIONS["values"].get(selected_option)
    
    if not assignment_group_id:
        return jsonify({
            "ServiceNow": "Érvénytelen csoport kiválasztás."
        }), 400

    # Jegy adatok ServiceNow-ba történő küldéshez
    ticket_data = {
        "short_description": short_description,
        "assignment_group": assignment_group_id,
        "priority": selected_priority,
        "caller_id": user_sys_id
    }

    # ServiceNow API hívás a jegy létrehozásához
    headers = {
        'Authorization': f'Bearer {user_token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        'https://dev227667.service-now.com/api/now/table/incident',
        headers=headers,
        json=ticket_data
    )

    if response.status_code == 201:
        result = response.json().get('result', {})
        ticket_number = result.get('number', 'N/A')
        return jsonify({
            "ServiceNow": f"Sikeresen létrehozta a hibajegyet a következő azonosítóval: {ticket_number}"
        }), 201
    else:
        return jsonify({
            "ServiceNow": "A hibajegy létrehozása sikertelen.",
            "details": response.text
        }), response.status_code

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
