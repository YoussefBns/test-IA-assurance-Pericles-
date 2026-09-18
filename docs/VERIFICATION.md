# Rapport de vérification de la livraison

## Résumé

**63 tests pytest réussis**, aucun échec dans la dernière exécution archivée. Un serveur Uvicorn réel a été démarré, interrogé en HTTP puis arrêté. Le notebook a été exécuté de haut en bas. Les deux modèles ML, le retrieval documentaire, les métriques et les imports de réponses batch ont été exécutés sur les fichiers fournis.

**Non vérifié en situation réelle :** build/run Docker, génération avec un vrai modèle Ollama, installation fraîche depuis Internet, exécution Windows et CI GitHub. **Push non effectué :** les appels GitHub, dont une tentative réelle de création de fichier, ont renvoyé 404.

## Commandes et preuves

| Commande / opération | Résultat | Preuve archivée |
|---|---|---|
| `python -m partie1_ml.train` | Deux modèles entraînés ; sélection avant lecture du test ; artefact rechargé identique | `evidence/train_run.log`, `../partie1_ml/outputs/metrics.json` |
| `python -m partie2_rag.pipeline ingest` / fonctions d'ingestion | 20 PDF, 110 chunks, index LSA64 persistant | `../partie2_rag/index/manifest.json` |
| `python -m partie2_rag.pipeline benchmark --generation none` | 15 recherches évaluées, génération laissée absente | `evidence/rag_retrieval_run.txt`, `../partie2_rag/results_retrieval.json` |
| `python -m partie2_rag.pipeline import-batch ...` | 15 réponses ChatGPT importées, hashes/citations vérifiés | `evidence/rag_batch_import.txt`, `../partie2_rag/results.json` |
| Tentative native Ollama, timeout 2 secondes | Échec de connexion au service local ; pas de modèle LLM exécuté | `evidence/ollama_attempt.json` |
| `python -m pytest -q --junitxml=docs/evidence/pytest.xml ...` | **63 passed**, 3,37 secondes dans cette exécution | `evidence/tests_final.txt`, `evidence/pytest.xml` |
| `python -m scripts.smoke_api` | Health 200 ; predict 200 ; entrée invalide 422 ; OpenAPI et log JSONL contrôlés | `evidence/http_smoke.json` |
| `python -m compileall -q partie1_ml partie2_rag partie3_mlops scripts tests` | Code de retour 0 | Vérification locale, sans prétendre à un lint complet |
| `python -m scripts.build_notebook` | 9 cellules de code exécutées, aucun output d'erreur | `evidence/notebook_execution.txt`, `../partie1_ml/notebook.ipynb` |
| `python -m scripts.smoke_docker` | Code 2 ; statut `not_executed`, Docker absent | `evidence/docker_smoke.json` |
| Compatibilité des métadonnées de dépendances installées | 113 relations vérifiées, aucune incompatible | `evidence/dependency_checks.json` |
| Lecture réseau de connectivité vers Hugging Face | Échec DNS ; aucune donnée utilisateur envoyée | `evidence/network_probe.json` |
| Lecture et tentative d'écriture GitHub | 404, aucune écriture réussie | `evidence/github_attempts.json` |

La couverture de lignes mesurée pendant pytest est d'environ **71 %** sur les modules sélectionnés, avec les limites de configuration du rapport. `train.py` a été exécuté séparément et apparaît à 0 % dans cette session de couverture pytest : cela ne signifie pas qu'il n'a pas été entraîné, ni que la suite couvre 100 % du code. Les tests du transport Ollama utilisent un serveur factice et n'attestent pas de la qualité d'un LLM.

## Contrôles de cohérence importants

La cible ne peut pas entrer dans le transformeur. Les partitions clients sont disjointes. Les médianes stockées correspondent exactement au train, et les probabilités après rechargement correspondent aux CSV de prédictions et aux métriques annoncées. Le vrai HTTP utilise le même pipeline que l'évaluation.

Les références RAG portent sur des textes et pages effectivement extraits. Les scores denses, lexicaux et de fusion restent distincts. Les sources de la réponse batch doivent appartenir au contexte du prompt dont l'empreinte est enregistrée. Ce dernier contrôle est syntaxique : il ne constitue pas une mesure de fidélité de chaque affirmation.

La copie du Dockerfile est identique à celui de la racine ; l'image est configurée pour embarquer le modèle et tourner sans root. Cette inspection **ne remplace pas** la construction et le test du conteneur. Le workflow CI est un fichier prêt à être utilisé, pas une CI qui aurait déjà passé.

## Revue et corrections

Une revue directe du code et des contrats a conduit à ajouter deux tests de régression : refuser une génération explicitement tronquée par limite de longueur, et refuser l'ingestion CLI lorsque les vingt fichiers du sujet ne sont pas tous présents. Les deux tests ont d'abord échoué, puis réussi après correction. Les traces historiques `tdd_*`, `regression_before_fixes.txt` et les résultats intermédiaires sont conservés comme preuves du développement ; **ils ne sont pas le résultat final**.

La convention des histogrammes de drift a été vérifiée contre celle utilisée lors de l'entraînement : intervalles NumPy fermés à gauche et ouverts à droite, plus une classe de manque. Cela évite une fausse dérive créée par une convention de bornes différente.

Il n'y a pas eu de revue par un agent indépendant ou un humain. L'assistance et l'annotation proviennent de la même session ChatGPT ; les limites d'indépendance sont explicites.

## Actions nécessaires hors de cet environnement

Vérifier l'image Docker sur une machine équipée, exécuter les quinze appels RAG avec le modèle local choisi et examiner les réponses, puis rétablir l'accès au dépôt privé pour publier. La cause exacte du 404 GitHub n'a pas été déterminée : le dépôt est listé, mais les accès par nom et par identifiant ont échoué. Aucune création de dépôt de remplacement, aucun changement de droits et aucun email de rendu n'ont été effectués.

## Vérification après extraction du ZIP

L’archive a été extraite dans un dossier distinct, puis les tests et le smoke test HTTP ont été relancés depuis cette copie. Résultat : **63 tests réussis en 2,42 secondes**, `/health` et `/predict` répondent en 200, l’entrée invalide est refusée en 422 et le journal JSONL est cohérent. Le serveur de vérification a été arrêté. Les preuves sont dans `evidence/zip_extraction_check.json`, `evidence/zip_extracted_pytest.txt` et `evidence/zip_extracted_http.txt`.

Cette vérification utilise les mêmes dépendances Python installées : elle contrôle l’autonomie des fichiers de l’archive, pas une installation fraîche, Windows ou Docker. Un manifeste SHA-256 couvre tous les fichiers livrés sauf le manifeste lui-même ; les caches Python, journaux applicatifs temporaires et secrets sont exclus du ZIP.
