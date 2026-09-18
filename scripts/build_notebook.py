"""Créer et exécuter le notebook de restitution depuis les artefacts calculés.

Le réentraînement reste une commande explicite, afin de ne pas écraser le
modèle validé simplement en ouvrant le notebook.
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    md = nbformat.v4.new_markdown_cell
    code = nbformat.v4.new_code_cell
    cells = [
        md("# Assurance — exploration, modèle et vérification\n\n"
           "Notebook exécuté de restitution du test. Les métriques affichées ont été calculées par "
           "`python -m partie1_ml.train`, qui exécute le split, la CV, l'évaluation, SHAP et la sérialisation. "
           "Ce notebook contrôle les artefacts et ne réentraîne pas implicitement sur le holdout. "
           "Assistance : ChatGPT ; relecture personnelle du candidat encore nécessaire."),
        code("from pathlib import Path\nimport json, hashlib\nimport numpy as np\nimport pandas as pd\nimport joblib\nfrom IPython.display import display, Image, Markdown\nROOT = Path.cwd()\nif not (ROOT / 'partie1_ml').exists():\n    ROOT = ROOT.parent\nassert (ROOT / 'partie1_ml/model.joblib').exists()\ndef read_json(path):\n    return json.loads((ROOT / path).read_text(encoding='utf-8'))\ndf = pd.read_csv(ROOT / 'data/dataset_assurance_churn.csv')\naudit = read_json('partie1_ml/outputs/dataset_audit.json')\nmeta = read_json('partie1_ml/metadata.json')\nmetrics = read_json('partie1_ml/outputs/metrics.json')\nprint({'clients': len(df), 'colonnes': len(df.columns), 'churn': float(df.churned.mean())})\nassert hashlib.sha256((ROOT / 'data/dataset_assurance_churn.csv').read_bytes()).hexdigest() == meta['dataset_sha256']"),
        md("## 1. Qualité et split avant les choix statistiques\n\n"
           "Le CSV original est conservé. Identifiants uniques, cible binaire, contrôles de domaine ; "
           "la date d'observation reste absente. L'EDA utilisée pour les décisions porte sur le train."),
        code("display(pd.DataFrame({'valeurs_manquantes': df.isna().sum(), 'type': df.dtypes.astype(str)}))\nsplit = read_json('partie1_ml/outputs/split_manifest.json')\nassert set(split['train_client_ids']).isdisjoint(split['test_client_ids'])\ntrain = df.set_index('client_id').loc[split['train_client_ids']].reset_index()\ntest = df.set_index('client_id').loc[split['test_client_ids']].reset_index()\nprint('Train / test :', len(train), len(test))\ndisplay(train.describe().round(3))"),
        md("### Extrêmes et valeurs manquantes\n\n"
           "Les sinistres élevés sont conservés ; log1p atténue la queue. L'imputation médiane "
           "avec indicateurs de manque est apprise dans chaque fold, jamais sur tout le fichier. "
           "Ni ancienneté reconstruite ni récence fondée sur la date actuelle."),
        code("display(read_json('partie1_ml/outputs/eda.json'))\ndisplay(Image(filename=str(ROOT / 'docs/figures/distribution_montant_sinistres_eur.png')))\ndisplay(Image(filename=str(ROOT / 'docs/figures/distribution_score_satisfaction.png')))"),
        md("## 2. Trois features métier partagées avec l'API\n\n"
           "Appels/(1+sinistres annuels), (5−satisfaction)×appels, retards×résiliation antérieure. "
           "Les unités et horizons sont compatibles ; ce sont des signaux associatifs, pas une rentabilité actuarielle. "
           "Les dates et l'identifiant ne sont pas des prédicteurs."),
        code("model = joblib.load(ROOT / 'partie1_ml/model.joblib')\ntransformed = model.named_steps['features'].transform(train.drop(columns='churned'))\nfrom partie1_ml.features import DERIVED, NUMERIC\ndisplay(transformed[DERIVED].head(8))\nassert not {'client_id','churned','date_souscription','date_derniere_interaction'} & set(transformed.columns)\nlearned = model.named_steps['preprocessor'].named_transformers_['num'].named_steps['imputer'].statistics_\nnp.testing.assert_allclose(learned, transformed[NUMERIC].median().to_numpy(), rtol=0, atol=0)\nprint('Médianes du train vérifiées.')"),
        md("## 3. Validation croisée et test final\n\n"
           "Deux modèles pondérés, cinq folds stratifiés, graine 42. Choix sur l'Average Precision de CV. "
           "Seuil fixé à 0,5 avant l'expérience. La forêt a un F1 test supérieur, mais le choix n'est pas changé après examen du holdout."),
        code("rows = []\nfor name, item in metrics['candidates'].items():\n    rows.append({'modele': name, 'AP_CV': item['cv_ap_mean'], 'ecart_type_CV': item['cv_ap_std'], **{k:v for k,v in item['holdout'].items() if k != 'confusion_matrix'}})\ndisplay(pd.DataFrame(rows).set_index('modele').round(4))\nprint('Sélection :', metrics['selected_model'])\nprint('Paramètres :', metrics['candidates'][metrics['selected_model']]['best_parameters'])\ndisplay(Image(filename=str(ROOT / 'docs/figures/roc.png')))\ndisplay(Image(filename=str(ROOT / 'docs/figures/precision_recall.png')))"),
        md("### Compromis de campagne et calibration\n\n"
           "66 churners détectés, 32 manqués, 108 faux positifs, 194 vrais négatifs. "
           "Le Brier pondéré est moins bon que la référence constante : les scores ne sont pas des probabilités calibrées. "
           "Sans coûts ni effet causal d'une action, aucun ROI n'est calculé."),
        code("from sklearn.metrics import roc_auc_score, confusion_matrix\np = model.predict_proba(test.drop(columns='churned'))[:,1]\nassert abs(roc_auc_score(test.churned, p) - meta['metrics']['auc_roc']) < 1e-12\nprint('AUC rechargée :', roc_auc_score(test.churned, p))\nprint('Intervalle bootstrap percentile, modèle fixé :', meta['holdout_auc_bootstrap_95_percentile'])\nprint('Brier dummy :', metrics['dummy_baseline']['brier'])\ndisplay(Image(filename=str(ROOT / 'docs/figures/confusion_matrix.png')))"),
        md("## 4. SHAP et permutation\n\n"
           "SHAP calculé sur 120 lignes du holdout avec 100 lignes de référence train. "
           "L'échelle de la régression est le log-odds. L'importance absolue n'indique pas la direction et ne prouve pas de causalité."),
        code("display(pd.read_csv(ROOT / 'partie1_ml/outputs/shap_importance.csv').head(10))\ndisplay(Image(filename=str(ROOT / 'docs/figures/shap_importance.png')))\nnames = model[:-1].get_feature_names_out()\ncoeff = pd.Series(model.named_steps['model'].coef_[0], index=names)\ndisplay(coeff.loc[['num__score_satisfaction','num__resiliation_anterieure','num__retard_paiement_nb','num__nb_sinistres_12m','num__anciennete_mois']])\ndisplay(Image(filename=str(ROOT / 'docs/figures/permutation_importance.png')))"),
        md("## 5. Artefact utilisé par l'API\n\n"
           "Le pipeline complet est chargé une fois, avec empreinte et métadonnées. L'exemple ci-dessous est synthétique. "
           "Le test HTTP réel est archivé séparément dans docs/evidence/http_smoke.json."),
        code("example = read_json('partie3_mlops/example_request.json')\nprint({'client_id':example['client_id'], 'probability':float(model.predict_proba(pd.DataFrame([example]))[0,1])})\nassert hashlib.sha256((ROOT / 'partie1_ml/model.joblib').read_bytes()).hexdigest() == meta['model_sha256']\ndisplay(read_json('docs/evidence/http_smoke.json')['health'])"),
        md("## 6. Résumé RAG, avec sa provenance réelle\n\n"
           "L'index LSA/NumPy, le retrieval et les scores sont exécutés. Les réponses jointes sont un lot ChatGPT orchestré manuellement, "
           "pas une preuve d'inférence Ollama autonome. La fidélité du lot n'est pas notée comme un benchmark indépendant."),
        code("rag = read_json('partie2_rag/results.json')\ndisplay(pd.DataFrame([{'question':r['question_id'], 'mode':r['mode'], 'P_at_5':r['metrics']['context_precision'], 'rappel_preuves':r['metrics']['evidence_recall'], 'generation':r['generation']['status']} for r in rag['runs']]))\nprint('Chunks :', rag['corpus']['n_chunks'])\nprint('Live API vérifiée :', rag['batch_import']['live_api_verified'])"),
        md("## Pour reproduire et poursuivre\n\n"
           "`python -m partie1_ml.train` relance les entraînements. `python -m pytest -q` contrôle la suite. "
           "`python -m scripts.smoke_docker` et le benchmark `--generation ollama` nécessitent les services correspondants. "
           "Les limitations et choix à défendre sont développés dans README.md et docs/DEBRIEF.md."),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    notebook.metadata['language_info'] = {'name': 'python', 'version': '3.13.5'}
    NotebookClient(notebook, timeout=90, kernel_name='python3', resources={'metadata': {'path': str(ROOT)}}).execute()
    path = ROOT / 'partie1_ml/notebook.ipynb'
    nbformat.write(notebook, path)
    print(f'Notebook exécuté : {path}; {sum(c.cell_type == "code" for c in cells)} cellules de code.')


if __name__ == '__main__':
    main()
