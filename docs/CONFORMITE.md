# Matrice de conformité au sujet

Le statut distingue implémentation et preuve d'exécution. Les points sont ceux du sujet, **pas une note auto-attribuée**.

| Exigence | Poids | Livrables / preuve | État réel |
|---|---:|---|---|
| EDA, manque, outliers justifiés | 8 | train.py, outputs/eda.json, figures, README | Exécuté sur train ; sources vérifiées |
| ≥ 3 features métier | 9 | features.py, tests/test_features.py | Implémenté et testé |
| ≥ 2 modèles, déséquilibre, CV stratifiée, holdout | 10 | train.py, cv_*.csv, metrics.json, partitions | Deux modèles entraînés et comparés ; holdout gelé |
| SHAP / importances, commentaire top 5 | 8 | shap_importance.csv, permutation_importance.csv, README | SHAP et permutation exécutés |
| Pipeline complet sérialisé | Livrable | model.joblib, metadata.json, test de rechargement | Livré, rechargé et comparé |
| 20 PDF, chunks, embeddings, vector store | 10 | ingest.py, index/, manifest.json | Exécuté : 110 chunks, LSA/NumPy ; pas de modèle neuronal ni FAISS |
| RAG : chunks, prompts, réponses | 10 | pipeline.py, generation.py, results.json/.md | Retrieval exécuté ; réponses batch ChatGPT tracées ; client Ollama codé, vraie génération locale non exécutée |
| ≥ 1 métrique et commentaire par question | 10 | annotations.json, evaluation.py, results.json, README | Précision de contexte mesurée ; annotations assistées non indépendantes |
| 2–3 améliorations et ≥ 1 mise en œuvre | 10 | hybrid, hybrid_filtered, comparaison | Deux variantes implémentées et mesurées ; reranker proposé non mesuré |
| POST /predict et GET /health | 8 | app.py, schemas.py, tests API, http_smoke.json | Tests et vrai HTTP réussis |
| Image Docker autonome | 8 | Dockerfile racine et copie, Compose, smoke_docker.py | Recette complète, inspection statique ; build/run non exécutés : Docker absent |
| Logs, drift, 2 indicateurs | 9 | app.py, monitoring.py, drift_reference.json, README | Logs HTTP vérifiés ; PSI testé ; rappel mature expliqué, non calculé sans labels |
| Pytest input/preprocessing/predict | +5 | tests/ et partie3_mlops/tests/ | Suite exécutée, résultats dans docs/evidence |
| Dépendances reproductibles | Transversal | requirements*.txt, environment_actual.json | Versions installées compatibles vérifiées ; installation réseau fraîche non exécutée |
| Notebook ou script structuré | Livrable | train.py et notebook.ipynb | Script exécuté ; notebook de restitution exécuté |
| Transparence assistance LLM | Transversal | README, DEBRIEF, batch provenance | ChatGPT déclaré ; aucune validation personnelle attribuée au candidat |
| Lien Git | Rendu | Dossier prêt, script de publication privé | Push tenté mais bloqué par HTTP 404 ; aucun dépôt modifié |

## Reste à vérifier avant une remise entièrement validée

Exécuter le build et smoke Docker dans un environnement disposant de Docker. Relancer la génération avec un vrai modèle Ollama et revoir les affirmations/citations des cinq questions, en particulier la complétude Q3. Confirmer l'accès au dépôt privé, puis publier. Ces opérations ne sont pas marquées terminées dans les preuves jointes.
