# Deriv Accumulator Bot 🤖📈

Un robot de trading algorithmique spécialisé **exclusivement** dans le trading des contrats **Accumulateurs** sur la plateforme [Deriv](https://deriv.com/). 

Ce bot est conçu pour appliquer une stratégie **"Sniper sur Bandes de Bollinger"** en s'appuyant sur les données **Tick par Tick**. Il combine des indicateurs techniques ultra-réactifs (Bandes de Bollinger, Volatilité sur Ticks) avec un modèle de **Machine Learning (Intelligence Artificielle)**. L'objectif est d'entrer sur le marché uniquement au moment le plus calme (Squeeze), de vérifier que l'IA valide la probabilité de succès, et de sécuriser des gains rapides avant une cassure (Knockout).

---

## 🌟 Caractéristiques Principales

- **Interface Bureau Moderne** : Contrôlez le bot depuis une interface graphique élégante (Dark Mode, Glassmorphism) sans avoir besoin de surveiller le terminal.
- **Ultra-Réactivité (Ticks)** : Le bot fonctionne désormais sur le flux de Ticks (et non plus sur des bougies d'une minute), lui permettant d'agir en une fraction de seconde sur l'Accumulateur.
- **Stratégie Bollinger Sniper (Squeeze)** : Le bot refuse de trader tant que le prix n'est pas strictement confiné dans les 40% centraux des Bandes de Bollinger. Il attend le point d'entrée le plus calme.
- **Filtres Anti-Bruit** : Un double filtre de Volatilité (écart-type des rendements) et de Momentum protège le bot des mouvements brusques.
- **Filtre IA (Machine Learning)** : Avant de lancer un trade, le bot consulte un modèle IA (Random Forest) entraîné sur la prédiction de danger à l'horizon de 3 ticks.
- **Auto-Amélioration (Dynamic Thresholding)** : Le bot adapte son niveau d'exigence (seuil de l'IA) en temps réel. S'il subit une perte, il devient plus strict ; s'il gagne, il maintient son seuil.
- **Take Profit Rapide (25%)** : Fini la cupidité ! Le bot vise une sortie rapide dès 25% de gains.
- **Sortie d'Urgence Dynamique** : Si le prix s'approche des 15% extérieurs des bandes pendant un trade, le bot force la clôture avant le Knockout.

---

## 🛠️ Architecture du Projet

```text
deriv_bot/
│
├── api/                   # Connexion à l'API de Deriv (WebSocket, REST, Exécution)
├── brain/                 # Cerveau du bot (Feature Engine, Filtre ML, Risk Manager)
├── data/                  # Collecte et mise en cache du flux de Ticks en temps réel
├── models/                # Contient le modèle d'IA entraîné (.joblib)
├── scripts/               # Scripts utilitaires (ex: entraînement du modèle IA)
├── utils/                 # Utilitaires (ex: configuration des logs)
│
├── .env                   # Fichier de configuration (Token API, etc.)
├── main.py                # Coeur du bot asynchrone (peut être exécuté sans interface)
├── gui.py                 # Interface Graphique Moderne (CustomTkinter)
└── requirements.txt       # Dépendances Python
```

---

## ⚙️ Prérequis et Installation

1. **Python 3.9+** doit être installé sur votre machine.
2. Clonez ou téléchargez ce dossier.
3. Installez les dépendances nécessaires via la commande :
   ```bash
   pip install -r requirements.txt
   ```
   > **Note :** Si l'interface ne se lance pas, assurez-vous d'avoir installé `customtkinter` (`pip install customtkinter`).

## 🔐 Configuration (`.env`)

Créez un fichier `.env` à la racine du projet s'il n'existe pas déjà et ajoutez vos informations d'identification Deriv :

```env
# Identifiants Deriv
DERIV_APP_ID=1089                 # ID de votre application Deriv
DERIV_PAT=votre_token_ici         # Personal Access Token (API Token)
DERIV_ACCOUNT_TYPE=demo           # "demo" ou "real"

# Paramètres de Trading
DERIV_SYMBOL=R_10                 # Volatility 10 Index
DERIV_GROWTH_RATE=0.05            # Taux de croissance de 5%
TAKE_PROFIT_PERCENT=25.0          # Prise de profit à 25%
```

> **Note :** Votre Token API (`DERIV_PAT`) doit avoir les permissions de **Lecture (Read)** et de **Trading (Trade)**.

---

## 🚀 Démarrage

Pour lancer l'interface graphique du robot, ouvrez un terminal et exécutez :

```bash
python gui.py
```

1. La fenêtre de contrôle s'affichera avec son thème sombre.
2. Cliquez sur le bouton **START BOT** pour lancer la connexion à Deriv.
3. Le tableau de bord affichera en temps réel les données de la stratégie (Prix, Squeeze, Volatilité) et la probabilité de l'Intelligence Artificielle.
4. Les logs du bot défileront directement dans la console intégrée au bas de l'écran.

---

## 🤖 Réentraîner l'Intelligence Artificielle

Si vous souhaitez que l'IA s'adapte aux toutes dernières données du marché, vous pouvez relancer son entraînement à tout moment :
```bash
python scripts/train_model.py
```
*(Attention : Assurez-vous d'adapter le script d'entraînement pour qu'il cible les Ticks et non les bougies OHLC, suite à la récente mise à jour de l'architecture).*

---

## ⚠️ Avertissement

Le trading comporte des risques élevés. Les performances passées d'un modèle de Machine Learning ne garantissent pas les résultats futurs. Ne tradez jamais de l'argent dont vous avez besoin. Il est fortement recommandé de tester longuement ce bot sur un compte **DEMO** avant d'envisager de l'utiliser en conditions réelles.
