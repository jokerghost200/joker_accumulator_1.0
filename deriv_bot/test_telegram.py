import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def test_message():
    print(f"Token: {TELEGRAM_BOT_TOKEN[:10]}... (caché pour sécurité)")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print("-" * 30)
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erreur : TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans le fichier .env")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "👋 <b>Bonjour Domy !</b>\nCeci est un test de connexion.",
        "parse_mode": "HTML"
    }

    print("Tentative d'envoi du message à Telegram...")
    try:
        # Timeout de 30 secondes pour être sûr
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            print("✅ SUCCÈS ! Le message a été envoyé.")
        else:
            print(f"❌ ÉCHEC de l'API. Code HTTP: {response.status_code}")
            print(f"Réponse détaillée: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ ERREUR: Le serveur Telegram met trop de temps à répondre (Timeout).")
        print("Votre connexion bloque peut-être l'accès à Telegram.")
    except Exception as e:
        print(f"❌ ERREUR inattendue: {e}")

if __name__ == "__main__":
    test_message()
