"""Compare Smart OPAC before and after MARC in a temporary catalog-only database."""
import argparse
import hashlib
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from statistics import mean
from time import perf_counter
from types import SimpleNamespace

from .enrich_opac_marc import apply_marc, stage_marc
from .evaluate_vector_index import retrieval_metrics
from app.database.connection import Store
from app.services.catalog import smart_catalog_search
from app.services.opac_catalog import BASE, stage_pack


def measure(state, cases):
    results=[]
    for case in cases:
        start=perf_counter()
        rows,meta=smart_catalog_search(state,case['q'],'all')
        relevant={BASE+identifier for identifier in case['relevant_ids']}
        urls=[row['source_url'] for row in rows]
        scores=retrieval_metrics(relevant,urls) if relevant else {
            'empty_correct':not urls and meta['guidance']==case.get('guidance',False)}
        results.append({'id':case['id'],'query':meta['interpretation'],'total':len(rows),
                        'elapsed_ms':round((perf_counter()-start)*1000,2),'top5':urls[:5],**scores})
    positive=[row for row in results if 'hit_at1' in row]
    negatives=[row['empty_correct'] for row in results if 'empty_correct' in row]
    return {'hit_at1':mean(row['hit_at1'] for row in positive),'ndcg_at5':mean(row['ndcg_at5'] for row in positive),
            'negative_correct':sum(negatives),'negative_cases':len(negatives),'cases':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    parser.add_argument('collection',type=Path)
    parser.add_argument('--cases',type=Path,default=Path('tests/evaluation/opac-marc-pilot.json'))
    args=parser.parse_args()
    cases_raw=args.cases.read_bytes()
    cases=json.loads(cases_raw)
    fields='id,title,author,year,kind,subjects,description,source_url,checked_at,published'
    with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)) as source:
        rows=source.execute(f'SELECT {fields} FROM books WHERE published=1 ORDER BY id').fetchall()
    available={row[7] for row in rows}
    if any(BASE+identifier not in available for case in cases for identifier in case['relevant_ids']):
        parser.error('Catalog is missing one or more pilot reference records.')
    books,pack=stage_pack(args.collection/'catalog-listings.jsonl',args.collection/'catalog-listings-manifest.json')
    records,report=stage_marc(args.collection/'records',{book.source_url for book in books})
    with tempfile.TemporaryDirectory() as directory:
        store=Store(Path(directory)/'catalog.sqlite3')
        with store.connect() as db:
            db.executemany(f'INSERT INTO books({fields}) VALUES (?,?,?,?,?,?,?,?,?,?)',rows)
        state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
        baseline=measure(state,cases)
        report['applied']=apply_marc(store.connect,records)
        enriched=measure(state,cases)
    print(json.dumps({'kind':'developer known-target pilot; no staff labels, live availability, vectors or LLM',
                      'catalog_count':len(rows),
                      'catalog_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest(),
                      'cases_sha256':hashlib.sha256(cases_raw).hexdigest(),'pack_sha256':pack['pack_sha256'],
                      'marc_sha256':hashlib.sha256(json.dumps(records,ensure_ascii=False).encode()).hexdigest(),
                      'marc':report,'baseline':baseline,'enriched':enriched},ensure_ascii=False))


if __name__=='__main__':
    main()
