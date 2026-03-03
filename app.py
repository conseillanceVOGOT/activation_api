from flask import Flask, request, jsonify
import json
import os
from datetime import datetime, timedelta
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__)

LICENCES_FILE = "licences.json"


# =====================================================
# UTILITAIRES LICENCES
# =====================================================

def load_licences():
    if not os.path.exists(LICENCES_FILE):
        return {"licences": []}
    with open(LICENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_licences(data):
    with open(LICENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def find_licence(licence_key):
    data = load_licences()
    for lic in data.get("licences", []):
        if lic.get("licence_key") == licence_key:
            return lic
    return None


def generate_licence(licence_type, siret):
    """
    Génère une clé de licence et une date d'expiration
    à partir du type et du SIRET.
    """
    if not siret or not siret.isdigit() or len(siret) != 14:
        return None, None

    # Clé de licence (même logique que ton ancien serveur)
    licence_key = f"VOGOT-{siret[-4:]}-{licence_type}"

    # Expiration
    if licence_type == "ANNUAL":
        expires = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    elif licence_type == "LIFETIME":
        expires = None
    elif licence_type == "FREE":
        expires = None
    else:
        return None, None

    return licence_key, expires


def add_licence_entry(licence_key, licence_type, siret, expires, provider, email=None, transaction_id=None):
    data = load_licences()

    entry = {
        "licence_key": licence_key,
        "type": licence_type,
        "siret": siret,
        "email": email,
        "produit": "Conseillance VOGOT",
        "active": True,
        "date_achat": datetime.now().strftime("%Y-%m-%d"),
        "expires": expires,
        "paiement": {
            "provider": provider,
            "transaction_id": transaction_id
        }
    }

    data.setdefault("licences", []).append(entry)
    save_licences(data)


# =====================================================
# WEBHOOKS STRIPE / PAYPAL
# =====================================================

@app.post("/api/webhook/stripe")
def webhook_stripe():
    """
    Webhook Stripe : on attend au minimum :
    {
        "licence_type": "ANNUAL" ou "LIFETIME",
        "siret": "12345678901234",
        "email": "client@example.com",
        "transaction_id": "xxx"  (optionnel)
    }
    """
    data = request.get_json() or {}

    licence_type = data.get("licence_type")
    siret = data.get("siret")
    email = data.get("email")
    transaction_id = data.get("transaction_id") or data.get("id")

    if licence_type not in ["ANNUAL", "LIFETIME", "FREE"]:
        return "invalid_licence_type", 400

    licence_key, expires = generate_licence(licence_type, siret)
    if not licence_key:
        return "invalid_siret_or_type", 400

    add_licence_entry(
        licence_key=licence_key,
        licence_type=licence_type,
        siret=siret,
        expires=expires,
        provider="stripe",
        email=email,
        transaction_id=transaction_id
    )

    return jsonify({
        "status": "ok",
        "licence_key": licence_key,
        "type": licence_type,
        "expires": expires
    }), 200


@app.post("/api/webhook/paypal")
def webhook_paypal():
    """
    Webhook PayPal : même format attendu que Stripe.
    """
    data = request.get_json() or {}

    licence_type = data.get("licence_type")
    siret = data.get("siret")
    email = data.get("email")
    transaction_id = data.get("transaction_id") or data.get("id")

    if licence_type not in ["ANNUAL", "LIFETIME", "FREE"]:
        return "invalid_licence_type", 400

    licence_key, expires = generate_licence(licence_type, siret)
    if not licence_key:
        return "invalid_siret_or_type", 400

    add_licence_entry(
        licence_key=licence_key,
        licence_type=licence_type,
        siret=siret,
        expires=expires,
        provider="paypal",
        email=email,
        transaction_id=transaction_id
    )

    return jsonify({
        "status": "ok",
        "licence_key": licence_key,
        "type": licence_type,
        "expires": expires
    }), 200


# =====================================================
# ENDPOINT D’ACTIVATION (LOGICIEL)
# =====================================================

@app.post("/activate")
def activate():
    data = request.get_json() or {}
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
# ENDPOINT COMPATIBLE AVEC TON LOGICIEL (SIRET)
# =====================================================

@app.post("/api/licence/verify")
def verify_licence():
    data = request.get_json() or {}
    siret = data.get("siret")
    licence_type = data.get("licence_type")

    # Vérification SIRET
    if not siret or not siret.isdigit() or len(siret) != 14:
        return jsonify({"status": "INVALID_SIRET"})

    # Génération de la licence
    licence_key, expires = generate_licence(licence_type, siret)
    if not licence_key:
        return jsonify({"status": "INVALID_TYPE"})

    # Enregistrement dans licences.json
    add_licence_entry(
        licence_key=licence_key,
        licence_type=licence_type,
        siret=siret,
        expires=expires,
        provider="manual"
    )

    return jsonify({
        "status": "OK",
        "licence_type": licence_type,
        "expires_at": expires,
        "licence_key": licence_key
    })

# =====================================================
# LANCEMENT LOCAL (debug)
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
