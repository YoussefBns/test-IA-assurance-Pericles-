# Test Technique — Consultant IA (Junior/Senior) - Periclès Group

| | |
|---|---|
| **Durée estimée** | 6 à 8 heures de travail effectif |
| **Délai de rendu** | 72 heures après réception |
| **Score total** | 100 points + 5 points bonus |
| **Rendu attendu** | Lien vers un repo Git (GitHub ou GitLab) |

---

## Consignes générales

Bienvenue dans ce test technique pour le poste Consultant IA chez Periclès Group. Il est conçu pour évaluer votre capacité à résoudre des problèmes concrets en ML, en IA générative et en MLOps dans un contexte **assurance**.

Il n'y a pas de réponse parfaite — ce qui nous intéresse, c'est votre **raisonnement**, la qualité de votre code et la clarté de vos décisions.

- Le travail est **individuel**. L'utilisation d'un LLM (Copilot, ChatGPT…) est autorisée à condition de le **mentionner** et d'être capable d'expliquer vos choix lors de l'entretien de debriefing.
- La partie 2 est **indépendante**  des parties 1 et 3 qui sont dépendantes — vous pouvez en traiter certaines partiellement si vous manquez de temps. Précisez dans votre README ce que vous n'avez pas eu le temps de faire.
- Commentez votre code. Un code illisible, même correct, sera pénalisé.
- Fournissez un fichier `requirements.txt` ou `pyproject.toml` permettant de reproduire votre environnement.

---

## Données fournies

### `dataset_assurance_churn.csv` — 2 000 clients, 20 colonnes

Ce dataset décrit des contrats d'assurance actifs ou résiliés sur la période 2022-2024.

| Colonne | Type | Description |
|---|---|---|
| `client_id` | str | Identifiant unique client |
| `age` | int | Âge du souscripteur |
| `situation_familiale` | str | Célibataire, En couple, Marié(e), Veuf/Veuve |
| `profession` | str | Salarié, Indépendant, Fonctionnaire, Retraité, Sans emploi |
| `region` | str | Région française de résidence |
| `anciennete_mois` | int | Durée du contrat en mois |
| `produit_principal` | str | Type de contrat (Auto, Habitation, Santé, Vie, Multirisque Pro) |
| `niveau_couverture` | str | Essentiel / Confort / Premium |
| `canal_souscription` | str | Agence, Web, Courtier, Téléphone |
| `prime_mensuelle_eur` | float | Prime mensuelle en euros |
| `nb_sinistres_12m` | int | Nombre de sinistres déclarés sur 12 mois |
| `montant_sinistres_eur` | float | Montant total des sinistres (euros) |
| `nb_appels_support_12m` | float | Appels au service client (contient des valeurs manquantes) |
| `nb_avenants_contrat` | int | Nombre de modifications de contrat |
| `retard_paiement_nb` | int | Nombre de retards de paiement |
| `score_satisfaction` | float | Score de satisfaction 1-5 (contient des valeurs manquantes) |
| `resiliation_anterieure` | int | Client ayant déjà résilié un contrat (0/1) |
| `date_souscription` | date | Date de souscription du contrat |
| `date_derniere_interaction` | date | Dernière interaction avec l'entreprise |
| `churned` | int | **Variable cible** : résiliation dans les 3 prochains mois (0/1) |

> **Taux de churn observé : ~25%** — le déséquilibre des classes est intentionnel et doit être géré.

### `fiches_produits/` — 20 fiches PDF

Fiches produit des 5 gammes d'assurance proposées (4 fiches par gamme : Essentiel, Confort, Premium + FAQ). Elles décrivent les garanties, franchises, exclusions, délais de carence et conditions de résiliation.

---

## Partie 1 — ML classique & Feature Engineering · 35 pts · ~2h30

### Contexte

Votre objectif est de **prédire le churn** des clients (colonne `churned`) à partir de leurs caractéristiques contractuelles et comportementales. Ce modèle doit pouvoir être mis en production pour alimenter une campagne de rétention proactive.

### Tâches

**1. Exploration & nettoyage — 8 pts**

Analysez la distribution des variables, traitez les valeurs manquantes (colonnes `score_satisfaction` et `nb_appels_support_12m`) et identifiez les outliers (notamment sur `montant_sinistres_eur`). Justifiez chaque décision de traitement dans un commentaire ou une cellule Markdown.

**2. Feature engineering — 9 pts**

Créez au minimum **3 features métier pertinentes** dans le contexte assurance. Quelques pistes (non exhaustives) :

- Ratio sinistres / ancienneté
- Coût moyen par sinistre
- Rentabilité estimée du contrat (prime × ancienneté − sinistres)
- Nombre de jours depuis la dernière interaction
- Score de risque composite

Expliquez pourquoi chaque feature est pertinente pour prédire le churn.

**3. Modélisation & évaluation — 10 pts**

Entraînez et comparez au moins **2 modèles** (ex. Logistic Regression + XGBoost ou LightGBM). Gérez le déséquilibre des classes (class_weight, SMOTE, ou autre). Utilisez une validation croisée stratifiée pour le tuning. Présentez les métriques finales sur un test holdout :

- AUC-ROC, Precision, Recall, F1-score
- Matrice de confusion commentée

**4. Interprétabilité — 8 pts**

Produisez une analyse **SHAP** ou feature importance sur le meilleur modèle. Commentez les 5 features les plus influentes : est-ce cohérent avec la réalité métier d'un assureur ?

### Livrables partie 1

- Un notebook Jupyter (ou script Python structuré) commenté
- Le modèle sérialisé (`model.joblib` ou équivalent)
- Un court paragraphe dans le README : choix du modèle, gestion du déséquilibre, limites identifiées

---

## Partie 2 — LLMs & IA Générative (RAG) · 40 pts · ~3h

### Contexte

Votre mission est de construire un **assistant conversationnel** capable de répondre aux questions des conseillers assurance sur les produits de la gamme, en se basant uniquement sur les fiches produit fournies.

### Tâches

**1. Pipeline d'ingestion — 10 pts**

Chargez et découpez les 20 fiches PDF en chunks. Générez des embeddings et stockez-les dans une vector store (FAISS ou ChromaDB recommandé). Justifiez votre stratégie de chunking : taille des chunks, overlap, éventuelles métadonnées attachées (produit, niveau de couverture…).

**2. Système de requêtage — 10 pts**

Implémentez un pipeline RAG complet. Pour chacune des 5 questions de test ci-dessous, affichez :
- Les N chunks retrieved (avec leur score de similarité)
- Le prompt envoyé au LLM
- La réponse générée

Utilisez le LLM de votre choix (OpenAI GPT-4o, Mistral, modèle HuggingFace local…).

**3. Évaluation de la qualité — 10 pts**

Choisissez et implémentez au moins **une métrique d'évaluation** parmi :
- `faithfulness` — la réponse est-elle fidèle aux chunks retrieved ?
- `answer_relevancy` — la réponse répond-elle à la question posée ?
- `context_precision` — les chunks retrieved sont-ils pertinents ?

Vous pouvez utiliser RAGAs, une évaluation LLM-as-judge, ou une grille manuelle structurée. Commentez les résultats pour chaque question.

**4. Amélioration — 10 pts**

Proposez **2 à 3 pistes d'amélioration concrètes** et implémentez-en au moins une. Montrez son impact sur les métriques. Exemples de pistes : re-ranking, hybrid search (dense + BM25), filtrage par métadonnées produit, reformulation de la query, prompt engineering.

### Questions de test à utiliser

| # | Question |
|---|---|
| Q1 | Quelles sont les garanties incluses dans la formule Confort de l'Assurance Habitation ? |
| Q2 | Quels sont les délais de carence pour une Assurance Santé niveau Essentiel ? |
| Q3 | Un client Multirisque Pro peut-il résilier son contrat avant l'échéance annuelle ? Si oui, sous quelles conditions ? |
| Q4 | Quelle est la franchise applicable en cas de bris de glace sur une Assurance Auto Premium ? |
| Q5 | Quelles exclusions de garantie s'appliquent à l'Assurance Vie pour les activités à risque ? |

### Livrables partie 2

- Le code du pipeline RAG (script ou notebook)
- Un fichier `results.json` avec les réponses et métriques par question
- Un paragraphe dans le README : choix du LLM, stratégie de chunking, résultats d'évaluation résumés

---

## Partie 3 — MLOps & Mise en Production · 25 pts · ~2h

### Contexte

Repartez du meilleur modèle de la Partie 1. L'objectif est de l'exposer comme une **API REST prête à déployer**, avec les bonnes pratiques de production.

### Tâches

**1. API REST avec FastAPI — 8 pts**

Créez un endpoint `POST /predict` qui accepte un JSON de features et retourne :
```json
{
  "client_id": "CLT00042",
  "churn_probability": 0.73,
  "prediction": 1,
  "risk_level": "élevé"
}
```
Ajoutez un endpoint `GET /health` retournant le statut et la version du modèle.

**2. Dockerisation — 8 pts**

Fournissez un `Dockerfile` fonctionnel. L'image doit se **builder et répondre à une requête** sans aucune configuration supplémentaire. Incluez un `docker-compose.yml` si pertinent. Exemple de commande de test attendue :

```bash
docker build -t churn-api .
docker run -p 8000:8000 churn-api
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" \
  -d '{"age": 45, "anciennete_mois": 24, "prime_mensuelle_eur": 95.0, ...}'
```

**3. Logging & monitoring — 9 pts**

Implémentez un mécanisme de **logging des inputs/outputs** de chaque prédiction (format libre : JSON lines, SQLite, CSV…). Expliquez dans le README :
- Comment ce logging permettrait de détecter du **data drift** dans un contexte assurance (ex. dérive sur `montant_sinistres_eur` après une catastrophe naturelle)
- 2 métriques à surveiller en priorité et pourquoi

**4. Bonus — Tests automatisés · +5 pts**

Écrivez des tests `pytest` couvrant au minimum :
- La validation des inputs (champ manquant, mauvais type)
- Le pipeline de preprocessing
- L'endpoint `/predict` avec des données valides

### Livrables partie 3

- `app.py` — API FastAPI
- `Dockerfile` (+ `docker-compose.yml` si applicable)
- `tests/` — tests pytest (bonus)
- Section **"Comment lancer l'API"** dans le README avec les commandes exactes

---

## Grille de notation

### Partie 1 — ML classique (35 pts)

| Critère | Points |
|---|:---:|
| Exploration & nettoyage (justifications incluses) | 8 |
| Feature engineering (pertinence métier assurance) | 9 |
| Modélisation, gestion du déséquilibre & métriques | 10 |
| Interprétabilité & analyse SHAP commentée | 8 |

### Partie 2 — LLMs & RAG (40 pts)

| Critère | Points |
|---|:---:|
| Pipeline d'ingestion (chunking, embeddings, stockage) | 10 |
| Système de requêtage (chunks + prompts + réponses affichés) | 10 |
| Évaluation de la qualité (métrique choisie & commentaire) | 10 |
| Amélioration implémentée & impact mesuré | 10 |

### Partie 3 — MLOps (25 pts)

| Critère | Points |
|---|:---:|
| API FastAPI fonctionnelle (/predict + /health) | 8 |
| Dockerisation (image qui build et répond) | 8 |
| Logging & stratégie de monitoring data drift | 9 |
| **Bonus** : tests pytest | +5 |

### Critères transversaux (évalués à l'entretien de debriefing)

- **Qualité du code** — structure claire, fonctions bien nommées, pas de code mort
- **Clarté du README** — peut-on reproduire votre travail en 5 minutes ?
- **Profondeur de l'analyse** — on cherche du raisonnement, pas juste du code qui tourne
- **Pragmatisme** — vos choix sont-ils justifiés ? assumez-vous vos trade-offs ?

---

## Structure attendue du repo

```
votre-nom-test-ia/
├── README.md                        # Vue d'ensemble & instructions de lancement
├── requirements.txt                 # Dépendances Python
├── data/
│   └── dataset_assurance_churn.csv  # (ne pas committer si > 50 Mo)
├── partie1_ml/
│   ├── notebook.ipynb               # Exploration, features, modèles
│   └── model.joblib                 # Modèle sérialisé
├── partie2_rag/
│   ├── pipeline.py                  # Ingestion + requêtage
│   └── results.json                 # Réponses + métriques par question
└── partie3_mlops/
    ├── app.py                       # API FastAPI
    ├── Dockerfile
    ├── docker-compose.yml           # (optionnel)
    └── tests/                       # Tests pytest (bonus)
        ├── test_api.py
        └── test_preprocessing.py
```

---

## Modalités de rendu

Merci d'envoyer le lien de votre repo Git à l'adresse suivante **avant expiration du délai** :

- **Email** : aalkarim@pericles-group.com et tsanson@pericles-group.com
- **Objet** : `[TEST TECHNIQUE IA] — Votre Nom`

En cas de question bloquante sur les données ou les consignes, contactez le recruteur. Une bonne question est un bon signal — n'hésitez pas.

---

> **Note** : il est tout à fait acceptable de ne pas tout finir. Ce qui compte avant tout, c'est la clarté de votre raisonnement et la qualité de ce que vous avez réalisé. Précisez dans votre README ce que vous auriez fait si vous aviez eu plus de temps.
