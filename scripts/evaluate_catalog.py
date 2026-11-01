"""Frozen public-metadata lookup checks, independent of LLM generation/training."""
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def metrics(relevant,returned):
    if not relevant:
        return {'empty_correct':not returned}
    top=returned[:5]
    return {'hit_at1':int(bool(returned) and returned[0] in relevant),
        'mrr_at5':next((1/i for i,value in enumerate(top,1) if value in relevant),0),
        'returned_precision_at5':sum(value in relevant for value in top)/max(1,len(top)),
        'recall_at20':len(set(returned[:20])&relevant)/len(relevant)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,default=ROOT/'tests/evaluation/catalog-lookup.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline-all',action='store_true',help='Measure the prior all-fields search without field routing.')
    args=parser.parse_args()
    from app.config import Settings
    from app.database.connection import Store
    from app.services.catalog import search_local
    pack=json.loads(args.cases.read_text(encoding='utf-8'))
    store=Store(Settings.load().data_dir/'library.sqlite3')
    with store.connect() as db:
        rows=[dict(row) for row in db.execute('SELECT * FROM books WHERE published=1 ORDER BY id')]
    digest=hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=pack['corpus_sha256'] or len(rows)!=pack['corpus_count']:
        parser.error('Catalog differs from frozen lookup corpus; review a new version instead of relabelling this measurement.')
    results=[]
    for case in pack['cases']:
        if case['field'] not in ('title','author'):
            parser.error('Unknown lookup field')
        start=perf_counter()
        found=search_local(store.connect,case['q']) if args.baseline_all else search_local(store.connect,case['q'],field=case['field'])
        urls=[row['source_url'] for row in found]
        results.append({'id':case['id'],'field':case['field'],'elapsed_ms':round((perf_counter()-start)*1000,2),
            'returned':len(urls),'top5':urls[:5],**metrics(set(case['relevant_urls']),urls)})
    summary={}
    for field in ('title','author'):
        positive=[row for row in results if row['field']==field and 'hit_at1' in row]
        summary[field]={'positive_cases':len(positive),**{key:round(mean(row[key] for row in positive),6)
            for key in ('hit_at1','mrr_at5','returned_precision_at5','recall_at20')},
            'mean_ms':round(mean(row['elapsed_ms'] for row in results if row['field']==field),2)}
    negative=[row for row in results if 'empty_correct' in row]
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'kind':pack['kind'],
        'execution':'prior all-fields baseline' if args.baseline_all else 'structured field routing',
        'corpus_sha256':digest,'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        'summary':summary,'negative_correct':sum(row['empty_correct'] for row in negative),
        'negative_cases':len(negative),'results':results,
        'limits':['Developer metadata lookup labels, not semantic relevance or staff-approved acceptance',
            'Returned precision uses only actual top5 results; empty positive results score zero',
            'Single local run; latency is not a concurrent SLA; no LLM or embedding inference']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('execution','summary','negative_correct','negative_cases')}))


if __name__=='__main__':
    main()
