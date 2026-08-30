import requests
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_chat_id():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    print("En attente de messages... Envoyez un message à votre bot (@Jokertradebot237bot) sur Telegram !")
    
    try:
        response = requests.get(url).json()
        if response.get("ok"):
            results = response.get("result", [])
            if not results:
                print("❌ Aucun message trouvé. Veuillez envoyer un message à votre bot, puis relancez ce script.")
            else:
                for res in results:
                    message = res.get("message", {})
                    chat = message.get("chat", {})
                    if chat:
                        chat_id = chat.get("id")
                        username = chat.get("username", "Inconnu")
                        print(f"✅ MESSAGE REÇU de @{username} !")
                        print(f"👉 VOTRE CHAT_ID EST : {chat_id}")
                        print("\nCopiez ce CHAT_ID et ajoutez-le dans votre fichier .env :")
                        print(f"TELEGRAM_CHAT_ID={chat_id}")
                        return
        else:
            print("Erreur de l'API Telegram:", response)
    except Exception as e:
        print("Erreur de connexion:", e)

if __name__ == "__main__":
    get_chat_id()
