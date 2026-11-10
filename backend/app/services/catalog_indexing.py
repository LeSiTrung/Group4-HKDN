"""Source excerpts for staff review. Suggestions never execute model instructions."""
import hashlib
import json
import re

from .catalog import item


def indexing_preview(row):
    raw=dict(row)
    revision=hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    book=item(raw)
    marc=book.get('marc',{})
    suggestions=[]
    known={value.strip().casefold() for value in book['subjects'].split(';') if value.strip()}
    subjects=[]
    for value in marc.get('subjects','').split(';'):
        value=value.strip()
        if value and value.casefold() not in known:
            subjects.append(value)
            known.add(value.casefold())
    if subjects:
        suggestions.append({'field':'subjects','value':'; '.join(subjects),
                            'source_field':'MARC — chủ đề','checked_at':marc['checked_at']})
    summary=marc.get('summary','').strip()
    if summary and summary not in book['description']:
        suggestions.append({'field':'summary','value':summary,
                            'source_field':'MARC — tóm tắt','checked_at':marc['checked_at']})
    classification=re.search(r'(?:Chỉ số Phân loại thập phân Dewey|DDC)\s*:\s*(\d{3}(?:\.\d+)?)(?=\s|$)',book['description'],re.I)
    return {'revision':revision,'source_url':book['source_url'],'suggestions':suggestions,
            'classification':classification[1] if classification else None,
            'checked_at':book['checked_at']}
