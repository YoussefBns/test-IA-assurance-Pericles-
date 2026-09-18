# Guide de débriefing

Ce guide explique ce qui a été construit, pas une expérience personnelle fictive. Le candidat doit lire le code, relancer les démonstrations et reformuler les choix avant l'entretien. L'assistance ChatGPT doit être mentionnée.

## Présentation en deux minutes

« J'ai séparé le projet en un pipeline de churn, un système documentaire et une API d'inférence. Le modèle livré est une régression logistique choisie sur validation croisée, pas sur le test. Il obtient une AUC proche de 0,70 mais produit beaucoup de faux positifs : je présente donc le compromis et les limites de calibration plutôt qu'un score flatteur. Le RAG conserve les pages et sections, compare trois recherches et documente ses sources ; le filtrage améliore la précision de contexte de 0,40 à 0,52 sur les cinq questions. L'API charge le même pipeline sérialisé, valide les entrées et journalise des variables utiles au drift. Les tests et le vrai HTTP ont été exécutés ; Docker et le backend LLM local restent à valider dans un environnement équipé. »

Ne pas réciter « j'ai fait » si cela masque l'assistance : préciser comment ChatGPT a contribué et ce qui a été personnellement vérifié.

## Questions ML à savoir expliquer

**Où une fuite pouvait-elle se produire ?** Dans une médiane calculée avant le split, un encodage appris sur tout le CSV, un choix de seuil sur le holdout, ou une feature de récence reconstruite avec une date d'observation inventée. Ici, le preprocessing reste dans le pipeline de CV ; les dates sont exclues faute de référence fiable.

**Pourquoi l'Average Precision en CV ?** La classe positive est minoritaire, et l'objectif exploratoire est de classer les clients à contacter. La sélection est fixée à l'avance. L'AUC complète le diagnostic, mais aucune des deux métriques ne donne un retour économique sans coûts ni efficacité de rétention.

**Pourquoi garder la régression alors que la forêt a un meilleur F1 sur test ?** Parce que changer de modèle après inspection du test ferait de ce test un outil de sélection. Le choix se fait sur l'AP de CV ; le F1 holdout reste un constat honnête.

**Pourquoi `class_weight` et pas SMOTE ?** C'est simple, intégré aux estimateurs et évite de générer des observations artificielles mêlant catégories et mesures. Ce n'est pas une preuve que SMOTE serait inférieur ; il n'a pas été comparé ici. La pondération ne remplace pas la calibration.

**Que signifient les 108 faux positifs ?** Des clients qui ne résilient pas dans le holdout mais qui seraient ciblés au seuil 0,5. On détecte 66 churners sur 98, pour 174 clients ciblés. L'intérêt commercial dépend du coût des contacts, de l'action proposée et de son effet causal, inconnus ici.

**Le score 0,73 signifie-t-il 73 % de risque réel ?** Pas de façon validée. Le modèle pondéré n'est pas calibré ; son Brier est moins bon que la fréquence constante. Le nom du champ vient du sujet. Une calibration sur validation séparée et une analyse métier sont nécessaires.

**Que prouvent les trois features ?** Qu'elles sont calculées et peuvent exprimer des interactions métier. Elles ne prouvent ni causalité ni gain marginal : aucune ablation isolant leur effet n'a été réalisée. Les dénominateurs nuls et les manques sont traités explicitement.

**Que dit SHAP ?** Il répartit le score autour d'une référence ; ici l'échelle est le log-odds. La magnitude absolue donne l'importance, pas le sens. Le sens des cinq variables principales a été vérifié dans les coefficients. Les corrélations et interactions rendent l'interprétation non causale.

## Questions RAG à savoir expliquer

**Quels embeddings ?** TF-IDF + SVD64 + normalisation L2, donc LSA. Aucun modèle neuronal téléchargé n'était disponible. C'est un vrai espace vectoriel appris sur le corpus, mais de qualité sémantique limitée hors vocabulaire. La recherche NumPy est exacte et adaptée au volume, sans prétendre être FAISS.

**Pourquoi garder la provenance de plusieurs pages ?** La question de résiliation de la FAQ Pro est en page 1 et sa réponse en page 2. Une extraction qui coupe chaque page sans recoller la section peut perdre les conditions essentielles. Les chunks portent l'intervalle de pages et le texte original.

**Quelle différence entre les scores ?** Le cosinus compare des vecteurs normalisés ; BM25 compare des occurrences lexicales pondérées ; RRF fusionne des rangs. Aucun de ces nombres n'est une probabilité de vérité. On ne les additionne pas directement.

**Quel gain a vraiment été mesuré ?** L'hybride seul ne change pas P@5. Le filtre produit/formule, FAQ préservées, fait passer la moyenne de 0,40 à 0,52. C'est un gain de 0,12 absolu sur cinq questions connues, pas une garantie de qualité générale. Les annotations sont assistées, pas validées par un expert indépendant.

**Pourquoi Q1 peut-elle s'améliorer sans atteindre une grande précision ?** Un seul passage, le tableau des garanties, suffit à apporter beaucoup de contenu métier, tandis que plusieurs tarifs polluent encore le top 5. Precision@5 mesure l'utilité des chunks selon la grille, pas directement la complétude de la réponse.

**Quelle limite importante reste en Q3 ?** Les conditions de la fiche Premium ne sont pas dans le top 5, bien que le corpus comporte une clause break à trois mois distincte du préavis d'un mois indiqué par la FAQ. L'analyse globale le signale, mais la réponse RAG ne doit pas injecter en secret un passage qu'elle n'a pas reçu.

**Qui a généré les réponses jointes ?** ChatGPT dans la conversation, à partir des prompts exportés, puis import contrôlé. Ce n'est pas le serveur Ollama. La session a vu les références complètes : ce lot n'est pas une évaluation aveugle. Pour une comparaison autonome, il faut relancer les quinze appels via Ollama et réexaminer leurs affirmations.

**Les citations suffisent-elles à garantir l'absence d'hallucination ?** Non. Le contrôle actuel vérifie les identifiants autorisés. Une citation syntaxiquement valide peut encore être attachée à une affirmation non supportée. Une revue des affirmations ou un juge indépendant serait nécessaire pour mesurer la fidélité.

## Questions API / MLOps

**Comment garantir l'identité entraînement/inférence ?** L'API charge le pipeline complet `model.joblib`, avec les classes dans des modules importables. Un test compare sa probabilité à celle de l'API. Les médianes ne sont pas recalculées au démarrage.

**Que se passe-t-il sans modèle ?** Le service reste non prêt : health et predict renvoient 503. Il n'y a pas de faux modèle de secours ou d'entraînement caché.

**Pourquoi les logs ne donnent-ils pas le rappel ?** Ils contiennent l'entrée et le score, pas la résiliation réellement observée trois mois plus tard. Il faut une cohorte mature et un rapprochement contrôlé des résultats. Un PSI élevé indique un changement de distribution, pas nécessairement un modèle devenu mauvais.

**Est-ce prêt pour une exposition publique ?** Non. C'est une API de démonstration avec recette de déploiement. TLS, authentification, supervision, rétention, contrôle de l'équité et validation métier sont encore nécessaires. Le build Docker n'a pas été exécuté dans ce runtime.

## Démonstration reproductible

Dans un environnement configuré : `python -m pytest -q`, puis `python -m scripts.smoke_api`. Montrer la matrice de confusion, ouvrir `partie2_rag/results.md`, comparer Q1 dense et filtrée, puis montrer Q3 et sa limite. Enfin, lancer `python -m scripts.smoke_docker` et le benchmark Ollama uniquement si les services sont disponibles ; conserver leurs vrais résultats.

## Vérifications personnelles avant remise

Lire `features.py`, `train.py`, `retrieval.py`, `pipeline.py` et `app.py`. Expliquer de mémoire le split, les trois features, le choix du modèle, le sens des erreurs et la provenance du lot RAG. Contrôler le caractère privé du dépôt. Ne pas présenter les tests d'un serveur factice comme une validation d'un vrai LLM ni une recette Docker comme un build réussi.
