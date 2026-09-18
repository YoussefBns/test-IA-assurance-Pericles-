# Plan d'exécution — test IA assurance

Spécification : `SUJET_ORIGINAL.md` et architecture détaillée approuvée dans la conversation.
Espace isolé : nouveau dossier `test-ia-pericles`, sans modification d'un dépôt existant.

1. **Données et ML** : vérifier les sources, réserver 20 % stratifiés ; écrire et exécuter les tests du transformeur ; implémenter preprocessing partagé, CV stratifiée LogisticRegression / RandomForest, seuil 0,5, métriques holdout, SHAP et sérialisation. Vérifier l'égalité après rechargement.
2. **RAG** : extraire les 36 pages des 20 PDF, conserver sections/pages et fenêtres sans mélange de documents ; tests chunking/index/métriques ; index dense LSA reproductible hors réseau, baseline et variantes hybrides, backend Ollama paramétrable. Archiver les prompts réellement construits. Ne pas présenter un appel LLM absent comme exécuté.
3. **API** : tests d'entrée puis FastAPI, charge unique de l'artefact, validation stricte, logs JSONL, monitoring ; smoke test HTTP et Docker lorsque disponible.
4. **Livraison** : scripts reproductibles, notebook exécuté, README et guide de débriefing, tests complets, matrice de conformité, ZIP et tentative de push autorisée.

## Contraintes constatées
- Python 3.13.5, CPU uniquement, environnement de calcul sans accès réseau sortant.
- Docker absent : la recette peut être écrite et auditée, pas annoncée comme exécutée ici.
- `testyouseff` apparaît dans la liste GitHub, mais lectures et création d'un fichier renvoient HTTP 404. Aucun fichier distant créé.
- Le repli dense LSA doit être clairement distingué d'embeddings neuronaux préentraînés ; il réalise une réduction TF-IDF/SVD, pas une émulation d'E5.
