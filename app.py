from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

LICENCES_FILE = "licences.json"


# =====================================================
# CHARGEMENT DES LICENCES
# =====================================================

def load_licences():
    if not os.path.exists(LICENCES_FILE):
        return {"licences": []}

    with open(LICENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_licence(licence_key):
    data = load_licences()
    for lic in data.get("licences", []):
        if lic.get("licence_key") == licence_key:
            return lic
    return None


# =====================================================
# ENDPOINT D’ACTIVATION
# =====================================================

@app.post("/activate")
def activate():
    data = request.get_json()
    licence_key = data.get("license_key")

    if not licence_key:
        return jsonify({"status": "invalid", "reason": "missing_key"})

    licence = find_licence(licence_key)

    # Licence inconnue
    if not licence:
        return jsonify({"status": "invalid", "reason": "not_found"})

    # Licence désactivée
    if not licence.get("active", True):
        return jsonify({"status": "invalid", "reason": "inactive"})

    lic_type = licence.get("type")
    expires = licence.get("expires")

    # FREE ou LIFETIME → toujours valides
    if lic_type in ["FREE", "LIFETIME"]:
        return jsonify({
            "status": "valid",
            "type": lic_type,
            "expires": expires
        })

    # ANNUAL → vérifier expiration
    if lic_type == "ANNUAL":
        if not expires:
            return jsonify({"status": "invalid", "reason": "missing_expiration"})

        exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
        today = datetime.today().date()

        if today <= exp_date:
            return jsonify({
                "status": "valid",
                "type": lic_type,
                "expires": expires
            })
        else:
            return jsonify({
                "status": "expired",
                "type": lic_type,
                "expires": expires
            })

    # Type inconnu
    return jsonify({"status": "invalid", "reason": "unknown_type"})


# =====================================================
# LANCEMENT
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
