"""Figures supplémentaires calculées à partir des sorties réelles gelées."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibrationDisplay

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = json.loads((ROOT / 'partie2_rag/results.json').read_text(encoding='utf-8'))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(5)
    for i, (mode, title) in enumerate([
        ('dense', 'Dense LSA'), ('hybrid', 'Hybride'),
        ('hybrid_filtered', 'Hybride + filtre'),
    ]):
        rows = [r for r in results['runs'] if r['mode'] == mode]
        ax.bar(x + (i-1)*.25, [r['metrics']['context_precision'] for r in rows],
               width=.25, label=title)
    ax.set_xticks(x, ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
    ax.set_ylim(0, 1)
    ax.set_ylabel('Précision de contexte @5')
    ax.set_title('Retrieval — cinq questions et annotations assistées')
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / 'docs/figures/rag_precision.png', dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for name, label in [('logistic_regression', 'Régression logistique'), ('random_forest', 'Random Forest')]:
        frame = pd.read_csv(ROOT / f'partie1_ml/outputs/predictions_{name}.csv')
        CalibrationDisplay.from_predictions(frame.y_true, frame.probability, n_bins=8,
                                            strategy='quantile', name=label, ax=ax)
    ax.set_title('Calibration sur holdout — diagnostic, pas réajustement')
    ax.set_xlabel('Score moyen prédit par tranche')
    ax.set_ylabel('Fréquence observée de churn dans la tranche')
    fig.tight_layout()
    fig.savefig(ROOT / 'docs/figures/calibration.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
