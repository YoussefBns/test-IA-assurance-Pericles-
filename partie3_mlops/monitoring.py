"""Drift exploratoire sur des JSONL d'inférence, sans labels de churn inventés."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def histogram(values, finite_edges):
    """Mêmes intervalles [gauche, droite[ que np.histogram du train, puis NaN."""
    edges = np.asarray(finite_edges, dtype=float)
    if not np.isfinite(edges).all() or np.any(np.diff(edges) <= 0):
        raise ValueError("Les bornes doivent être finies et strictement croissantes.")
    arr = np.asarray([float(v) if v is not None else np.nan for v in values])
    if np.isinf(arr).any():
        raise ValueError("Les valeurs infinies ne sont pas des données manquantes.")
    counts = np.histogram(arr[np.isfinite(arr)], [-np.inf, *edges, np.inf])[0]
    return counts.tolist() + [int(np.isnan(arr).sum())]


def psi(reference_counts, current_counts, smoothing=0.5):
    """Population Stability Index, lissage additif de 0,5 observation par classe.

    Zéro pour des distributions identiques. Ce n'est pas un test statistique
    ni une preuve de baisse de qualité du modèle. Les petits volumes sont instables.
    """
    ref = np.asarray(reference_counts, dtype=float)
    now = np.asarray(current_counts, dtype=float)
    if (ref.ndim != 1 or ref.shape != now.shape or ref.size == 0
            or not np.isfinite(ref).all() or not np.isfinite(now).all()
            or np.any(ref < 0) or np.any(now < 0)
            or ref.sum() <= 0 or now.sum() <= 0 or smoothing <= 0):
        raise ValueError("Effectifs non négatifs, non vides et dimensions égales requis.")
    p = (ref + smoothing) / (ref.sum() + smoothing * len(ref))
    q = (now + smoothing) / (now.sum() + smoothing * len(now))
    return float(np.sum((q - p) * np.log(q / p)))


def analyze_logs(log_path: Path, reference_path: Path):
    """Analyser une fenêtre de logs explicite ; aucune extrapolation temporelle."""
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    rows = []
    for number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Ligne JSON invalide : {number}") from exc
        if row.get("status") == "ok":
            rows.append(row)
    if not rows:
        return {"status": "no_data", "n": 0, "drift": None}
    drift = {}
    for name, base in reference.items():
        values = [r["inputs"].get(name) for r in rows]
        counts = histogram(values, base["finite_edges"])
        drift[name] = {
            "psi": psi(base["counts"], counts),
            "reference_counts": base["counts"],
            "current_counts": counts,
            "finite_edges": base["finite_edges"],
            "missing_rate": sum(v is None for v in values) / len(values),
        }
    return {
        "status": "analyzed",
        "n": len(rows),
        "reference_n": next(iter(reference.values()))["n"],
        "timestamp_min": min(r["timestamp_utc"] for r in rows),
        "timestamp_max": max(r["timestamp_utc"] for r in rows),
        "model_versions": sorted({r["model_version"] for r in rows}),
        "drift": drift,
        "predicted_high_risk_rate": sum(r["output"]["prediction"] for r in rows) / len(rows),
        "latency_p95_ms": float(np.quantile([r["duration_ms"] for r in rows], .95)),
        "observed_recall": None,
        "warning": "Fenêtre fournie uniquement. Aucun label à trois mois : rappel réel non mesurable. Seuils PSI non validés métier. Ne pas mélanger plusieurs versions sans analyse dédiée.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / "partie1_ml/drift_reference.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze_logs(args.logs, args.reference)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
