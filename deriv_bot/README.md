# Deriv Accumulator Bot 🤖📈

Un robot de trading algorithmique spécialisé **exclusivement** dans le trading des contrats **Accumulateurs** sur la plateforme [Deriv](https://deriv.com/). 

Ce bot est conçu pour appliquer une stratégie **"Sniper sur Bandes de Bollinger"** en s'appuyant sur les données **Tick par Tick**. Il combine des indicateurs techniques ultra-réactifs avec un modèle de **Machine Learning probabiliste**. L'objectif est d'entrer sur le marché au moment le plus calme (Squeeze), de simuler le contrat pour vérifier sa probabilité de survie face aux barrières dynamiques de Deriv, et d'optimiser le taux de croissance (Growth Rate).

---

## 🌟 Caractéristiques Principales

- **Interface Bureau Moderne** : Contrôlez le bot depuis une interface graphique élégante (Dark Mode, Glassmorphism). Configurez la mise initiale, le taux de croissance, et les objectifs de session directement depuis l'application.
- **Ultra-Réactivité (Ticks)** : Le bot fonctionne sur le flux de Ticks pour une réactivité à la fraction de seconde.
- **Moteur IA Probabiliste Orienté Survie** : L'IA ne prédit plus simplement "HAUT" ou "BAS". Elle estime la **probabilité de survie** du contrat (ex: P(Survie 8 ticks) = 91%) en fonction du taux de croissance et des barrières (Knockout thresholds).
- **Auto-Sélection du Taux de Croissance** : Si le paramètre `Auto` est sélectionné dans l'interface, le bot interrogera l'API pour les 5 taux (1% à 5%) et choisira intelligemment le taux offrant le meilleur compromis rendement/risque.
- **Objectifs de Session (Cooldowns) & Perte Maximale (Max Loss)** : Le bot peut être configuré pour faire une pause après avoir atteint un certain profit (ex: 5$). Il inclut également un arrêt d'urgence configurable (Max Loss) pour protéger votre capital en cas de série de pertes (ex: arrêt si -20$).
- **Filtres Anti-Bruit & Squeeze** : Refuse de trader tant que le prix n'est pas confiné au centre des bandes de Bollinger, et utilise des filtres de Volatilité et de Momentum.
- **Auto-Amélioration (On-the-Fly Retraining)** : Dès que le bot subit une perte, il extrait les données de cette erreur, lance un ré-entraînement ultra-rapide en tâche de fond (sans vous déconnecter), et met à jour son modèle XGBoost instantanément pour ne plus refaire cette erreur.
- **Gestion Dynamique du Risque (Prudence Mode)** : Le bot démarre avec une exigence de sécurité élevée (80%). S'il génère un profit satisfaisant (ex: > 3$), il passe en "Mode Prudence" (85%) pour sécuriser vos gains jusqu'à la fin de l'objectif. S'il subit une perte, il devient temporairement paranoïaque (90%) le temps de reprendre confiance.

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

## 🔐 Configuration (`.env`)

Créez un fichier `.env` à la racine du projet s'il n'existe pas déjà et ajoutez vos informations d'identification Deriv :

```env
# Identifiants Deriv
DERIV_APP_ID=1089                 # ID de votre application Deriv
DERIV_PAT=votre_token_ici         # Personal Access Token (API Token)
DERIV_ACCOUNT_TYPE=demo           # "demo" ou "real"

# Paramètres de Trading (Surchargés par l'Interface)
DERIV_SYMBOL=R_10                 
TAKE_PROFIT_PERCENT=25.0          # Prise de profit du contrat à 25%
```

> **Note :** Votre Token API (`DERIV_PAT`) doit avoir les permissions de **Lecture (Read)** et de **Trading (Trade)**.

---

## 🚀 Démarrage

Pour lancer l'interface graphique du robot, ouvrez un terminal et exécutez :

```bash
python gui.py
```

1. Configurez votre **Stake (Mise Initiale)**.
2. Choisissez un **Taux de Croissance (1% à 5%)**, ou laissez sur **Auto** pour que l'IA choisisse le meilleur taux dynamiquement.
3. Définissez vos objectifs de session : **Profit Target** (déclenche le temps de pause/cooldown) et **Perte Max** (déclenche l'arrêt d'urgence du bot).
4. Cliquez sur **START BOT** pour lancer la connexion à Deriv.

---

## 🤖 Réentraîner l'Intelligence Artificielle

Bien que le bot apprenne de ses erreurs "à la volée" (On-the-fly) pendant que vous tradez, vous pouvez également relancer son entraînement complet depuis zéro à tout moment (par exemple, au début d'une nouvelle journée) :
```bash
python scripts/train_model.py
```

---

## ⚠️ Avertissement

Le trading comporte des risques élevés. Les performances passées d'un modèle de Machine Learning ne garantissent pas les résultats futurs. Ne tradez jamais de l'argent dont vous avez besoin. Il est fortement recommandé de tester longuement ce bot sur un compte **DEMO** avant d'envisager de l'utiliser en conditions réelles.
