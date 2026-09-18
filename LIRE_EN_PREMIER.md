# Ouvrir le projet

Le dossier contient le code, les données fournies, le modèle entraîné, les résultats, le notebook exécuté, les tests et les commandes de lancement. **Ce n'est pas seulement un prompt ou un squelette.**

Commencer par `README.md` pour lancer l'API. `partie1_ml/notebook.ipynb` montre les résultats du churn. `partie2_rag/results.md` présente les passages, prompts, réponses et métriques des cinq questions. `docs/DEBRIEF.md` prépare l'entretien.

## Ce qui a été exécuté

Deux modèles entraînés sur le vrai CSV ; meilleur modèle retenu sur CV. AUC holdout 0,6994. Extraction des vingt PDF et comparaison de trois stratégies de retrieval. API testée en vrai HTTP. 63 tests pytest réussis. Notebook exécuté.

## Ce qui reste à vérifier

Docker n'était pas installé dans l'environnement de réalisation : la recette est fournie mais pas validée par un build. Le client Ollama est codé, mais aucun vrai modèle local n'était accessible ; les réponses jointes sont un lot ChatGPT orchestré manuellement, avec cette provenance explicitement enregistrée. Le push GitHub a échoué en 404 ; aucun fichier n'a été publié.

Pour ces vérifications, les commandes et leurs prérequis sont dans le README. Le script `PUSH_GITHUB.ps1` ne publie qu'après confirmation, refuse un dépôt distant non vide et n'utilise jamais force-push.

Le sujet autorise l'assistance IA si elle est déclarée. Relire le code et les limites avant l'entretien ; ne pas présenter le dossier comme personnellement vérifié tant que cela n'a pas été fait.
