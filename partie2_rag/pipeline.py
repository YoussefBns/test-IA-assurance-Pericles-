"""CLI RAG : ingestion, requête, conversation et benchmark traçable.

Aucun résultat de génération n'est fabriqué lorsque le service est absent.
Les imports de lots ChatGPT sont identifiés séparément des appels HTTP live.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

from partie2_rag.ingest import extract_corpus
from partie2_rag.retrieval import Retriever, build_index, write_json
from partie2_rag.evaluation import relevance_metrics
from partie2_rag.generation import OllamaClient, build_messages, citation_audit, prompt_hash

ROOT=Path(__file__).resolve().parents[1]
MODES=('dense','hybrid','hybrid_filtered')

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def load_annotations(path,chunks):
    raw=read_json(path);byid={c['chunk_id']:c for c in chunks};result={}
    for question,rows in raw['annotations'].items():
        ids=[]
        for row in rows:
            c=byid.get(row['chunk_id'])
            if c is None or c['text']!=row['evidence_text'] or c['document']!=row['document'] or c['pages']!=row['pages']:
                raise ValueError(f'Annotation obsolète ou non étayée : {row["chunk_id"]}')
            ids.append(row['chunk_id'])
        if not ids or len(set(ids))!=len(ids):raise ValueError('Annotations absentes ou dupliquées.')
        result[question]=ids
    return result

def benchmark(index_dir,questions_path,annotations_path,generation='none',client=None,top_k=5):
    if generation not in {'none','ollama'}:raise ValueError('Backend invalide.')
    retriever=Retriever(index_dir)
    annotations=load_annotations(annotations_path,retriever.chunks)
    questions=read_json(questions_path)
    results=[]
    for question in questions:
        qid=question['id'];text=question['question']
        if qid not in annotations:raise ValueError(f'Annotation absente : {qid}')
        for mode in MODES:
            started=time.perf_counter();chunks=retriever.search(text,top_k,mode)
            elapsed=time.perf_counter()-started
            messages=build_messages(text,chunks)
            row={'question_id':qid,'question':text,'mode':mode,'chunks':chunks,'messages':messages,
                'prompt_sha256':prompt_hash(messages),'retrieval_seconds':elapsed,
                'metrics':relevance_metrics([c['chunk_id'] for c in chunks],annotations[qid]),
                'answer':None,'citations':None,
                'generation':{'status':'not_run','execution':None,'reason':'Génération non demandée pour ce run de retrieval.'}}
            if generation=='ollama':
                try:
                    generated=(client or OllamaClient()).generate(messages)
                    row['answer']=generated.pop('answer');row['generation']=generated
                    row['citations']=citation_audit(row['answer'],chunks)
                except RuntimeError as exc:
                    row['generation']={'status':'failed','execution':'live_ollama_attempt','reason':str(exc)}
            results.append(row)
    summary={mode:{key:statistics.mean(r['metrics'][key] for r in results if r['mode']==mode and r['metrics'][key] is not None)
        for key in ('context_precision','ranked_context_precision','evidence_recall')} for mode in MODES}
    summary['differences']={mode:{key:summary[mode][key]-summary['dense'][key]
        for key in ('context_precision','ranked_context_precision','evidence_recall')} for mode in MODES[1:]}
    return {'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'corpus':retriever.manifest,'top_k':top_k,'retrieval_modes':list(MODES),
        'annotations_sha256':hashlib.sha256(Path(annotations_path).read_bytes()).hexdigest(),
        'evaluation':{'context_precision':'Precision@N = chunks pertinents / chunks retournés (non RAGAs)',
            'ranked_context_precision':'Moyenne des Precision@k aux rangs pertinents retrouvés',
            'evidence_recall':'Chunks pertinents retrouvés / chunks annotés pertinents',
            'annotations_origin':read_json(annotations_path)['origin'],
            'limitations':'Cinq questions connues ; comparaison exploratoire ; annotations assistées non indépendantes ; aucune mesure automatique de fidélité des réponses.'},
        'runs':results,'summary':summary}

def attach_batch_answers(result,batch):
    """Importer des sorties manuellement orchestrées, jamais les rebaptiser live."""
    if batch.get('execution')!='chatgpt_interactive_batch':
        raise ValueError('Seuls les lots explicitement interactifs sont acceptés ici.')
    output=copy.deepcopy(result);bykey={(r['question_id'],r['mode']):r for r in output['runs']}
    seen=set()
    for response in batch['responses']:
        key=(response['question_id'],response['mode'])
        row=bykey.get(key)
        if row is None or response.get('prompt_sha256')!=row['prompt_sha256']:
            raise ValueError('Le hash du prompt ou la question ne correspond pas au lot exporté.')
        if key in seen:raise ValueError('Réponse dupliquée dans le lot.')
        seen.add(key)
        answer=response.get('answer')
        if not isinstance(answer,str) or not answer.strip():raise ValueError('Réponse batch vide.')
        audit=citation_audit(answer,row['chunks'])
        if audit['invalid_ids']:raise ValueError('Citation hors contexte dans le lot.')
        row['answer']=answer;row['citations']=audit
        row['generation']={'status':'generated_interactive_batch','execution':'chatgpt_interactive_batch',
            'model':batch.get('model'),'live_api_verified':False,'duration_seconds':None,
            'provenance':batch.get('provenance'),
            'limitations':batch.get('limitations')}
    output['batch_import']={'n_responses':len(seen),'model':batch.get('model'),'execution':batch['execution'],
        'live_api_verified':False,'limitations':batch.get('limitations')}
    return output

def markdown_export(result):
    parts=['# Benchmark RAG — traces complètes','',
        'Les scores de retrieval sont calculés. Le mode de génération de chaque réponse est indiqué. Les lots interactifs ne prouvent pas un appel API autonome.','']
    for row in result['runs']:
        parts += [f"## {row['question_id']} / {row['mode']}",'',row['question'],'',
            f"Génération : `{row['generation']['status']}`. Prompt SHA-256 : `{row['prompt_sha256']}`.",
            f"Métriques : `{json.dumps(row['metrics'],ensure_ascii=False)}`",'',
            '### Passages retrouvés','']
        for chunk in row['chunks']:
            parts += [f"#### Rang {chunk['rank']} — {chunk['chunk_id']}",
                f"{chunk['document']} · pages {chunk['pages']} · cosinus {chunk['similarity_cosine']:.6f} · BM25 {chunk['bm25_score']:.6f} · RRF {chunk['rrf_score']}",'',chunk['text'],'']
        parts += ['### Messages exacts construits','', '```json',json.dumps(row['messages'],ensure_ascii=False,indent=2),'```','',
            '### Réponse','',row['answer'] or 'Non générée. Aucun texte de remplacement fictif.','']
    return '\n'.join(parts)

def make_client(args):
    return OllamaClient(args.model,args.ollama_url,args.timeout)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    ingest=sub.add_parser('ingest');ingest.add_argument('--pdf-dir',type=Path,default=ROOT/'data/fiches_produits');ingest.add_argument('--index',type=Path,default=ROOT/'partie2_rag/index')
    bench=sub.add_parser('benchmark');bench.add_argument('--generation',choices=['none','ollama'],default='none');bench.add_argument('--output',type=Path,default=ROOT/'partie2_rag/results_retrieval.json')
    bench.add_argument('--questions',type=Path,default=ROOT/'partie2_rag/questions.json');bench.add_argument('--annotations',type=Path,default=ROOT/'partie2_rag/annotations.json')
    ask=sub.add_parser('ask');ask.add_argument('question');ask.add_argument('--contexts-only',action='store_true')
    chat=sub.add_parser('chat')
    imp=sub.add_parser('import-batch');imp.add_argument('--retrieval',type=Path,required=True);imp.add_argument('--batch',type=Path,required=True);imp.add_argument('--output',type=Path,required=True)
    for p in [bench,ask,chat]:
        p.add_argument('--index',type=Path,default=ROOT/'partie2_rag/index');p.add_argument('--top-k',type=int,default=5)
        p.add_argument('--model',default=os.getenv('OLLAMA_MODEL','qwen2.5:1.5b'));p.add_argument('--ollama-url',default=os.getenv('OLLAMA_URL','http://127.0.0.1:11434'));p.add_argument('--timeout',type=float,default=180)
    for p in [ask,chat]:p.add_argument('--mode',choices=MODES,default='hybrid_filtered')
    args=parser.parse_args(argv)
    try:
        if args.command=='ingest':
            files=list(args.pdf_dir.glob('*.pdf'))
            expected={f'fiche_{product}_{level}.pdf' for product in ('auto','habitation','sante','vie','pro') for level in ('essentiel','confort','premium','faq')}
            if {p.name for p in files} != expected:
                raise ValueError('Le corpus du sujet doit contenir exactement les vingt fiches attendues.')
            result=build_index(extract_corpus(args.pdf_dir),args.index);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command in {'benchmark','import-batch'}:
            if args.command=='benchmark':
                result=benchmark(args.index,args.questions,args.annotations,args.generation,make_client(args),args.top_k)
            else:result=attach_batch_answers(read_json(args.retrieval),read_json(args.batch))
            args.output.parent.mkdir(parents=True,exist_ok=True);write_json(args.output,result)
            args.output.with_suffix('.md').write_text(markdown_export(result),encoding='utf-8')
            print(json.dumps(result['summary'],ensure_ascii=False,indent=2));print(f'Traces : {args.output}')
            return 2 if any(r['generation']['status']=='failed' for r in result['runs']) else 0
        retriever=Retriever(args.index);client=make_client(args);history=[];last_question=None
        while True:
            question=args.question if args.command=='ask' else input('Question (quit pour terminer) > ').strip()
            if question.lower() in {'quit','exit'}:return 0
            # Une relance elliptique emprunte le sujet de la question précédente,
            # jamais une affirmation d'une réponse comme preuve documentaire.
            query=question
            if args.command=='chat' and last_question and Retriever.filters(question)[0] is None:
                query=last_question+'\n'+question
            chunks=retriever.search(query,args.top_k,args.mode)
            messages=build_messages(question,chunks,history)
            print(json.dumps({'chunks':chunks,'messages':messages,'prompt_sha256':prompt_hash(messages)},ensure_ascii=False,indent=2))
            if args.command=='ask' and args.contexts_only:return 0
            generated=client.generate(messages);print('\n'+generated['answer'])
            print(json.dumps(citation_audit(generated['answer'],chunks),ensure_ascii=False))
            if args.command=='ask':return 0
            history.extend([{'role':'user','content':question},{'role':'assistant','content':generated['answer']}]);history=history[-4:];last_question=query[-4000:]
    except (ValueError,FileNotFoundError,RuntimeError,EOFError) as exc:
        print(f'Erreur : {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
