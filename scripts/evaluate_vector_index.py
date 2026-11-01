"""Measure the actual chunk/Qdrant path; never retrain or tune frozen cases."""
import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT))


def retrieval_metrics(relevant,returned):
    top=list(dict.fromkeys(returned))[:5]
    dcg=sum(1/math.log2(rank+1) for rank,url in enumerate(top,1) if url in relevant)
    ideal=sum(1/math.log2(rank+1) for rank in range(1,min(5,len(relevant))+1))
    return {'hit_at1':int(bool(top) and top[0] in relevant),'hit_at5':int(bool(set(top)&relevant)),
        'mrr_at5':next((1/rank for rank,url in enumerate(top,1) if url in relevant),0),
        'recall_at5':len(set(top)&relevant)/max(1,len(relevant)),'ndcg_at5':dcg/ideal if ideal else 0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--split',choices=('dev','test'),default='test')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from app.config import Settings
    from app.database.connection import Store
    from app.services.catalog import book_documents,item
    from app.services.rag_service import VectorIndex,row_fingerprint
    from training.prepare_data import load_frozen_dataset
    settings=Settings.load(args.data_dir.resolve() if args.data_dir else None)
    if os.getenv('QDRANT_URL','').strip():
        parser.error('This measured operator workflow uses local Qdrant only; stop its owning API first.')
    if not (settings.data_dir/'library.sqlite3').is_file():
        parser.error('Existing public catalog snapshot required')
    manifest,_,splits=load_frozen_dataset(args.dataset)
    store=Store(settings.data_dir/'library.sqlite3')
    def catalog():
        with store.connect() as db:
            return [item(r) for r in db.execute('SELECT * FROM books WHERE published=1 ORDER BY id')]
    books=catalog()
    corpus_hash=row_fingerprint(books)
    documents=book_documents(books)
    sources={row['id']:row['source_url'] for row in books}
    index=VectorIndex(settings)
    try:
        index._init(model=False)
        if not index.client.collection_exists(index._collection('books')):
            parser.error('Prebuild books index before measurement; construction time is reported separately.')
        index.rebuild(documents,namespace='books')
        results=[]
        for case in splits[args.split]:
            relevant={'https://thuvienso.ut.edu.vn/items/'+identifier for identifier in case['relevant_ids']}
            start=perf_counter()
            bounded=len(case['query'].encode('utf-8'))<=384
            returned=[sources[row['id']] for row,_ in index.search(case['query'],documents,namespace='books')] if bounded else []
            results.append({'id':case['group_id'],'within_query_budget':bounded,'returned':returned[:5],
                'elapsed_ms':round((perf_counter()-start)*1000,2),**retrieval_metrics(relevant,returned)})
        if row_fingerprint(catalog())!=corpus_hash:
            raise RuntimeError('Catalog changed during measurement; refuse a mixed snapshot result')
        eligible=[row for row in results if row['within_query_budget']]
        def summary(rows):
            return {'cases':len(rows),**{key:round(mean(row[key] for row in rows),6) if rows else 0
                for key in ('hit_at1','hit_at5','mrr_at5','recall_at5','ndcg_at5')},
                'mean_ms':round(mean(row['elapsed_ms'] for row in rows),2) if rows else 0}
        report={'recorded_at':datetime.now(timezone.utc).isoformat(),
            'kind':'synthetic frozen metadata queries through actual chunk/Qdrant path; not staff acceptance',
            'split':args.split,'dataset_manifest_sha256':hashlib.sha256((args.dataset/'manifest.json').read_bytes()).hexdigest(),
            'corpus_sha256':corpus_hash,'catalog_records':len(books),'training_manifest':manifest,
            'index':index.status(),'summary_all':summary(results),'summary_within_query_budget':summary(eligible),
            'query_budget_fallbacks':len(results)-len(eligible),'results':results,
            'limits':['Vector subpath only: six chunk hits,0.45 threshold,source deduplication and384-byte query guard unchanged',
                'Over-budget queries remain in all-case denominator with zero vector hits; normal app lexical fallback is separate',
                'No model training/threshold tuning or LLM invocation; full-text training scores are not directly comparable',
                'Existing index prep excluded; first lazy model load included in query timing; not a latency SLA']}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({key:report[key] for key in ('summary_all','summary_within_query_budget','query_budget_fallbacks','index')}))
    finally:
        index.close()


if __name__=='__main__':
    main()
