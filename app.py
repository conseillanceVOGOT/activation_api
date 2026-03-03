from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

# Charger les licences depuis le fichier JSON
def load_licenses():
    with open("licenses.json", "r") as f:
        return json.load(f)

@app.route('/activate', methods=['POST'])
def activate():
    data = request.get_json()
    license_key = data.get("license_key")

    licenses = load_licenses()

    # Vérifier si la clé existe
    if license_key not in licenses:
        return jsonify({"status": "invalid"})

    lic = licenses[license_key]
    lic_type = lic["type"]
    expires = lic["expires"]

    # FREE et LIFETIME : toujours valides
    if lic_type in ["FREE", "LIFETIME"]:
        return jsonify({"status": "valid", "type": lic_type})

    # ANNUAL : vérifier la date d'expiration
    if lic_type == "ANNUAL":
        if expires is None:
            return jsonify({"status": "invalid"})

        exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
        today = datetime.today().date()

        if today <= exp_date:
            return jsonify({"status": "valid", "type": lic_type, "expires": expires})
        else:
            return jsonify({"status": "expired", "type": lic_type, "expires": expires})

    return jsonify({"status": "invalid"})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
