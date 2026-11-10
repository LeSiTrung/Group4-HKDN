"""Stage verified MARC metadata. Run from the repo with python -m scripts.enrich_opac_marc."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .collect_opac import read_snapshot
from app.database.connection import Store
from app.services.knowledge import today
from app.services.opac_catalog import BASE, stage_pack


def stage_marc(directory, urls):
    records=[]
    report={'eligible':len(urls),'staged':0,'invalid':0,'missing':0,'empty':0}
    for url in sorted(urls):
        path=directory / (url.removeprefix(BASE)+'.json')
        if not path.is_file():
            report['missing']+=1
            continue
        snapshot=read_snapshot(path,url)
        if not snapshot:
            report['invalid']+=1
            continue
        checked=datetime.fromisoformat(snapshot['fetched_at']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
        if checked>today():
            report['invalid']+=1
            continue
        values={'subjects':[],'summary':[],'audience':[]}
        for field in snapshot['record']['marc']:
            tag=field['tag']
            if tag not in ('650','653','520','521'):
                continue
            subject=tag in ('650','653')
            allowed='axyzv' if tag=='650' else 'a'
            subfields=re.findall(r'\$([a-z0-9])([^$]+)',field['value'])
            text=(' — ' if subject else ' ').join(
                ' '.join(value.split()) for code,value in subfields if code in allowed and value.strip())
            key='subjects' if subject else ('summary' if tag=='520' else 'audience')
            if text and len(text)<=(240 if subject else 2400) and text not in values[key]:
                values[key].append(text)
        subjects='; '.join(values['subjects'][:8])
        summary=next(iter(values['summary']),'')
        audience=next(iter(values['audience']),'')
        if subjects or summary or audience:
            records.append((url,checked.isoformat(),snapshot['sha256'],subjects,summary,audience))
        else:
            report['empty']+=1
    report['staged']=len(records)
    return records,report


def apply_marc(db_factory, records):
    with db_factory() as db:
        db.execute('BEGIN IMMEDIATE')
        return db.executemany("""
            INSERT INTO book_marc (book_id,source_url,checked_at,snapshot_sha256,subjects,summary,audience)
            SELECT id,source_url,?,?,?,?,? FROM books WHERE source_url=? AND published=1
            ON CONFLICT(book_id) DO UPDATE SET
                source_url=excluded.source_url, checked_at=excluded.checked_at,
                snapshot_sha256=excluded.snapshot_sha256, subjects=excluded.subjects,
                summary=excluded.summary, audience=excluded.audience
            WHERE book_marc.source_url<>excluded.source_url OR book_marc.checked_at<excluded.checked_at
        """,((*metadata,url) for url,*metadata in records)).rowcount


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('collection',type=Path)
    parser.add_argument('--apply',type=Path,metavar='LIBRARY_SQLITE',help='Enrich an existing catalog database.')
    args=parser.parse_args()
    if args.apply and not args.apply.is_file():
        parser.error('--apply requires an existing catalog database.')
    if not (args.collection/'records').is_dir():
        parser.error('Missing collector records directory.')
    books,inventory=stage_pack(args.collection/'catalog-listings.jsonl',args.collection/'catalog-listings-manifest.json')
    records,report=stage_marc(args.collection/'records',{book.source_url for book in books})
    report.update(pack_sha256=inventory['pack_sha256'],applied=0)
    if args.apply and records:
        report['applied']=apply_marc(Store(args.apply).connect,records)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
