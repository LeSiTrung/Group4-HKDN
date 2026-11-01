"""Validate public DSpace snapshots before importing bibliographic metadata."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from .catalog import BookInput, save_book
from .rag_service import normalize


def _values(metadata, key):
    rows=metadata.get(key,[])
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('value'),str) for row in rows):
        raise ValueError('invalid_metadata')
    return list(dict.fromkeys(row['value'].strip() for row in rows if row['value'].strip()))


def normalize_snapshot(snapshot, *, published=False):
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('record'),dict):
        raise ValueError('invalid_snapshot')
    record=snapshot['record']
    try:
        identifier=str(UUID(record['uuid']))
    except (ValueError,TypeError,KeyError,AttributeError):
        raise ValueError('source_identity') from None
    if record['uuid']!=identifier or snapshot.get('source_url')!='https://thuvienso.ut.edu.vn/items/'+identifier:
        raise ValueError('source_identity')
    digest=hashlib.sha256(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    if snapshot.get('sha256')!=digest:
        raise ValueError('integrity')
    if record.get('type')!='item':
        raise ValueError('not_item')
    if record.get('inArchive') is not True or record.get('withdrawn') is not False or record.get('discoverable') is not True:
        raise ValueError('not_public_archived')
    try:
        fetched=datetime.fromisoformat(snapshot['fetched_at'].replace('Z','+00:00'))
        if fetched.tzinfo is None:
            raise ValueError
        checked_at=fetched.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    except (ValueError,TypeError,KeyError,AttributeError):
        raise ValueError('timestamp') from None
    title=record.get('name')
    if not isinstance(title,str) or not title.strip():
        raise ValueError('missing_title')
    metadata=record.get('metadata')
    if not isinstance(metadata,dict):
        raise ValueError('invalid_metadata')
    authors=[]
    for value in _values(metadata,'dc.contributor.author'):
        for author in value.split(';'):
            if author.strip() and not re.match(r'^(gvhd|cbhd|nguoi huong dan|huong dan khoa hoc)(?:\s|$)',normalize(author)):
                authors.append(author.strip())
    years={value[:4] for value in _values(metadata,'dc.date.issued') if re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?',value)}
    subject_keys=[key for key in metadata if key=='dc.subject' or key.startswith('dc.subject.') or key=='creativework.keywords']
    subjects=list(dict.fromkeys(value for key in subject_keys+['dc.type'] for value in _values(metadata,key)))
    try:
        return BookInput(title=title,author='; '.join(dict.fromkeys(authors)),year=next(iter(years)) if len(years)==1 else '',
            subjects='; '.join(subjects),description='\n'.join(_values(metadata,'dc.description.abstract')),
            source_url=snapshot['source_url'],checked_at=checked_at,kind='digital',published=published)
    except ValidationError as error:
        fields=','.join(sorted({str(item['loc'][0]) for item in error.errors()}))
        raise ValueError('field_limits:'+fields) from None


def stage_snapshots(directory, *, published=False):
    files=sorted(Path(directory).glob('*.json'))
    books=[]
    report={'discovered':len(files),'accepted':0,'rejected':[]}
    for path in files:
        try:
            if path.stat().st_size>2_097_152:
                raise ValueError('snapshot_too_large')
            try:
                snapshot=json.loads(path.read_text(encoding='utf-8'))
            except (ValueError,UnicodeError,RecursionError):
                raise ValueError('invalid_json') from None
            book=normalize_snapshot(snapshot,published=published)
            if path.stem!=book.source_url.rsplit('/',1)[-1]:
                raise ValueError('filename_identity')
            books.append(book)
        except (OSError,ValueError,TypeError,RecursionError) as error:
            reason=str(error) if type(error) is ValueError else 'invalid_snapshot'
            report['rejected'].append({'file':path.name,'reason':reason})
    report['accepted']=len(books)
    return books,report


def import_books(db_factory, books):
    imported=0
    with db_factory() as db:
        db.execute('BEGIN IMMEDIATE')
        for book in books:
            if db.execute('SELECT 1 FROM books WHERE source_url=?',(book.source_url,)).fetchone():
                continue
            save_book(db,book)
            imported+=1
        db.execute("INSERT INTO audit(action,target) VALUES ('book.dspace_import',?)",(str(imported),))
    return {'imported':imported,'skipped_existing':len(books)-imported}
