"""Curated metadata snapshots, distinct from live library circulation state."""
import json
import re
import os
from datetime import date
from difflib import SequenceMatcher
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .knowledge import KnowledgeInput, today
from .rag_service import normalize, tokens


class BookInput(BaseModel):
    title:str=Field(min_length=1,max_length=500)
    author:str=Field(default='',max_length=300)
    year:str=Field(default='',pattern=r'^(?:\d{4})?$')
    kind:Literal['books','digital']='books'
    subjects:str=Field(default='',max_length=1000)
    description:str=Field(default='',max_length=8000)
    source_url:str=Field(max_length=1000)
    checked_at:date
    published:bool=False

    @field_validator('title')
    @classmethod
    def title_value(cls,value):
        if not value.strip():
            raise ValueError('Nhan đề không được trống.')
        return value.strip()

    @field_validator('source_url')
    @classmethod
    def source_value(cls,value):
        return KnowledgeInput.safe_url(value)

    @field_validator('checked_at')
    @classmethod
    def date_value(cls,value):
        if value>today():
            raise ValueError('Ngày rà soát không được ở tương lai.')
        return value


def item(row):
    row=dict(row)
    row['url']=row['source_url']
    row['published']=bool(row['published'])
    return row


def save_book(db,body,row_id=None):
    values=body.model_dump(mode='json')
    if row_id is None:
        row_id=db.execute(f"INSERT INTO books({','.join(values)}) VALUES ({','.join('?' for _ in values)})",tuple(values.values())).lastrowid
    else:
        db.execute(f"UPDATE books SET {','.join(k+'=?' for k in values)} WHERE id=?",(*values.values(),row_id))
    return item(db.execute('SELECT * FROM books WHERE id=?',(row_id,)).fetchone())


def seed_books(db_factory,path):
    with db_factory() as db:
        if db.execute("SELECT 1 FROM meta WHERE key='books_seeded'").fetchone():
            return
        for value in json.loads(path.read_text(encoding='utf-8')):
            body=BookInput(**value)
            if not db.execute('SELECT 1 FROM books WHERE source_url=?',(body.source_url,)).fetchone():
                save_book(db,body)
        db.execute("INSERT INTO meta VALUES ('books_seeded','1')")


def search_local(db_factory,query,kind='all'):
    with db_factory() as db:
        rows=db.execute('SELECT * FROM books WHERE published=1'+(' AND kind=?' if kind!='all' else ''),(() if kind=='all' else (kind,))).fetchall()
    words=tokens(query)-{'tim','sach','tai','lieu','theo','quyen','cuon','tac','gia','chu','de','nguoi','viet'}
    if not words:
        return []
    ranked=[]
    for row in rows:
        text=normalize(' '.join(row[k] for k in ('title','author','year','subjects','description')))
        corpus=set(text.split())
        matched=sum(any(w==t or (len(w)>=4 and len(t)>=4 and SequenceMatcher(None,w,t).ratio()>=0.83) for t in corpus) for w in words)
        coverage=matched/len(words)
        if coverage<0.6:
            continue
        title_hits=len(words&tokens(row['title']))
        author_hits=len(words&tokens(row['author']))
        ranked.append((item(row),coverage+title_hits*0.15+author_hits*0.1))
    ranked.sort(key=lambda pair:(-pair[1],pair[0]['id']))
    return [r for r,_ in ranked]


def public_book(db_factory,row_id):
    with db_factory() as db:
        row=db.execute('SELECT * FROM books WHERE id=? AND published=1',(row_id,)).fetchone()
    return item(row) if row else None


def search_books(state,query,kind='all'):
    matched=search_local(state.db,query,kind)
    if matched or state.settings.testing or os.getenv('ENABLE_VECTORS','true').lower()!='true':
        return matched
    with state.db() as db:
        rows=[item(r) for r in db.execute('SELECT * FROM books WHERE published=1'+(' AND kind=?' if kind!='all' else ''),(() if kind=='all' else (kind,)))]
    documents=[{'id':r['id'],'question':r['title'],'aliases':[r['author'],r['subjects']],'answer':r['description'] or r['title']} for r in rows]
    if not documents:
        return []
    try:
        hits=state.vectors.search(query,documents,namespace='books')
    except Exception:
        return []
    results=[]
    for row,_ in hits:
        current=public_book(state.db,row['id'])
        if current:
            results.append(current)
    return results


def is_book_request(question):
    q=normalize(question)
    if re.search(r'\bco (sach|cuon|quyen)\b',q) and re.search(r'\b(qua han|phi|phat|han tra|gia han)\b',q):
        return False
    return bool(re.search(r'\b(tim (?:sach|tai lieu|cuon|quyen)|tra cuu (?:sach|tai lieu)|co (?:sach|cuon|quyen) .+|sach ve|sach cua|sach tuong tu|goi y sach|sach danh cho)\b',q)) and not any(x in q for x in ('huong dan','cach tim','lam sao','nhu the nao','o dau','vao dau'))


def book_attribute(question):
    q=normalize(question)
    for attribute,pattern in (
        ('availability',r'con ban|con sach|co san|con khong|tinh trang|con muon|muon duoc|bao nhieu ban|so ban'),
        ('isbn',r'isbn'),('shelf',r'o ke|ke nao|xep gia|vi tri'),
        ('publisher',r'nha xuat ban'),('author',r'tac gia|ai viet|nguoi viet'),
        ('year',r'xuat ban|nam nao'),
    ):
        if re.search(r'\b(?:'+pattern+r')\b',q):
            return attribute
    return None


def book_followup(question):
    q=normalize(question)
    return bool(re.search(r'^(co cuon|cuon nao|sach nay|sach do|cuon nay|cuon do|con khong|con ban|con sach|con muon|co san|danh cho|nguoi moi|nang cao|tuong tu|tac gia|ai viet|nam xuat ban|xuat ban|isbn|o ke|co bao nhieu ban)',q)) and not any(x in q for x in ('huong dan','cach tim','nhu the nao'))


def book_query(question):
    q=normalize(question)
    q=re.split(r'\b(?:con muon|muon duoc|con ban|con sach|co san|bao nhieu ban|tinh trang)\b',q,maxsplit=1)[0]
    q=re.sub(r'\b(toi|minh|ban|co|khong|tim|sach|tai lieu|tra cuu|ve|theo|cho|giup|quyen|cuon|nao|danh|nguoi|viet|muon|goi y|tuong tu|cua)\b',' ',q)
    return ' '.join(q.split())


def contextual_question(question,history):
    q=normalize(question)
    if is_book_request(question) and not re.search(r'^co (?:cuon|quyen|sach) (?:nao|do|nay)\b',q):
        return question
    if re.fullmatch(r'(?:co so|cs)\s*[123]',q):
        previous=next((m['content'] for m in reversed(history or []) if m['role']=='user'),None)
        if previous and any(x in normalize(previous) for x in ('mo cua','gio phuc vu','lich phuc vu')):
            return previous+' '+question
    if not book_followup(question):
        return question
    attribute=book_attribute(question)
    for turn in reversed(history or []):
        if turn.get('context_query'):
            return 'Tìm sách về '+turn['context_query']+('' if attribute else ' '+question)
        if turn['role']=='user':
            if is_book_request(turn['content']):
                return 'Tìm sách về '+book_query(turn['content'])+('' if attribute else ' '+question)
            if not book_followup(turn['content']):
                break
    return question
