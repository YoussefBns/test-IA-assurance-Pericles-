"""Métriques exactes à partir de références structurées revues passage par passage.

context_precision désigne ici Precision@N, PAS la formule RAGAs. La variante
sensible au rang est fournie séparément, ainsi que le rappel des chunks probants.
"""
from __future__ import annotations

def relevance_metrics(retrieved_ids,relevant_ids):
    relevant=set(relevant_ids)
    if not relevant:raise ValueError('Annotations manquantes : impossible de mesurer la pertinence.')
    ids=list(retrieved_ids)
    if len(ids)!=len(set(ids)):raise ValueError('Chunks dupliqués dans le retrieval.')
    if not ids:
        return {'context_precision':None,'ranked_context_precision':None,'evidence_recall':0.,'n_retrieved':0,'n_relevant':0,'status':'no_context'}
    labels=[int(i in relevant) for i in ids];hits=sum(labels)
    running=0;weighted=0.
    for k,label in enumerate(labels,1):
        running+=label
        if label:weighted+=running/k
    return {'context_precision':hits/len(ids),'ranked_context_precision':weighted/hits if hits else 0.,
        'evidence_recall':hits/len(relevant),'n_retrieved':len(ids),'n_relevant':hits,'status':'evaluated'}
