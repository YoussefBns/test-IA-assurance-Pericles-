# Règles du projet

La spécification d'origine est `docs/SUJET_ORIGINAL.md`.

- Préserver les données brutes, les partitions train/test et les résultats réellement calculés.
- Ne pas inventer une métrique, un appel LLM, un build Docker ou un push.
- Ne jamais apprendre le preprocessing ou choisir le modèle sur le holdout.
- Partager le même pipeline entre entraînement et API ; ne pas déplacer les classes sérialisées sans migration.
- Garder les versions de scikit-learn identiques à celles des artefacts, ou réentraîner/reconstruire.
- Les réponses métier ne peuvent utiliser que les PDF fournis.
- Ne pas convertir les réponses batch ChatGPT en prétendus appels Ollama live.
- Exécuter `python -m pytest`, `python -m scripts.smoke_api` et, si Docker est disponible, `python -m scripts.smoke_docker`.
- Aucun secret, poids LLM ni log de prédiction utilisateur dans Git.
- Ne pas publier les documents du test sur un dépôt public sans autorisation.
