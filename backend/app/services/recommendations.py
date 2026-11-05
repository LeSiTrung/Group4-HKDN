"""Recommendations from published catalog metadata, never model-created books."""
import re

from .catalog import book_query, search_books
from .rag_service import normalize, tokens
from .llm_service import extract_book_topic

BEGINNER=r'nguoi moi(?: bat dau)?|moi(?: bat dau)? hoc|tu dau|nhap mon|co ban|beginner|introduction|introductory|fundamentals'
ADVANCED=r'nang cao|chuyen sau|advanced'
TEACHING=r'giao trinh|bai giang|tu hoc|textbook'


def is_recommendation_request(question):
    return bool(re.search(r'\b(?:goi y|de xuat|tu van|gioi thieu|tu hoc|de hoc|muon hoc|moi hoc|dang hoc|hoc.+nen doc|sach nao hoc|giup.+hieu|tim hieu|ky nang|kien thuc|cai thien|nen doc|'+BEGINNER+'|'+ADVANCED+r')\b',normalize(question)))


def recommendation_topic(question):
    q=normalize(question)
    level='beginner' if re.search(r'\b(?:'+BEGINNER+r')\b',q) else 'advanced' if re.search(r'\b(?:'+ADVANCED+r')\b',q) else None
    q=re.sub(r'\b(?:(?:danh )?cho )?(?:hoc )?(?:'+BEGINNER+'|'+ADVANCED+r')\b',' ',q)
    q=re.sub(r'\b(?:(?:de|muon|can|nen|dang|toi|minh|em) hoc|sach nao hoc|tu hoc)\b',' ',q)
    q=book_query(q)
    q=re.sub(r'^hoc\b',' ',q)
    q=re.sub(r'\b(?:tot hon|de lam do an|cho de hieu|nen doc|nen hoc|bat dau|mot so|tim hieu|ky nang|kien thuc|cai thien)\b',' ',q)
    q=re.sub(r'\b(?:hay|cac|vai|de|nganh|can|gi|nen|hon|tot|dang|them|duoc|khong|bat|dau|the|nhe|em)\b',' ',q)
    q=re.sub(r'\b(?:it|cntt)\b','công nghệ thông tin',q)
    return ' '.join(q.split()),level


def recommend_books(state,question):
    query,level=recommendation_topic(question)
    if not query:
        return {'books':[], 'query':'', 'level':level, 'level_unconfirmed':False, 'used_model':False}
    expanded=re.sub(r'\b(?:it|cntt)\b','công nghệ thông tin',question,flags=re.I)
    planned=extract_book_topic(expanded) if not state.settings.testing else None
    planned=recommendation_topic(planned)[0] if planned else None
    books=search_books(state,planned or query)
    if planned and not books:
        planned=None
        books=search_books(state,query)
    query=planned or query
    preferred=[]
    for book in books:
        text=normalize(book['title']+' '+book['description'])
        positive=bool(re.search(r'\b(?:'+(BEGINNER if level=='beginner' else ADVANCED)+r')\b',text)) if level else False
        opposite=bool(re.search(r'\b(?:'+(ADVANCED if level=='beginner' else BEGINNER)+r')\b',text)) if level else False
        if positive and not opposite:
            preferred.append(book['id'])
    if preferred:
        books=[b for b in books if b['id'] in preferred]
    elif level:
        # Unlabelled books remain related suggestions, not verified level matches.
        opposite=ADVANCED if level=='beginner' else BEGINNER
        books=[b for b in books if not re.search(r'\b(?:'+opposite+r')\b',normalize(b['title']+' '+b['description']))]
    words=tokens(query)
    books.sort(key=lambda b:(-bool(re.search(r'\b(?:'+TEACHING+r')\b',normalize(b['title']))),
                             -len(words&tokens(b['title'])),b['id']))
    selected=[]
    seen=set()
    requested=re.search(r'\b0*([1-9][0-9]*) (?:cuon|quyen|sach|tai lieu)\b',normalize(question))
    # Two significant digits suffice for the five-book cap, even for huge inputs.
    limit=min(int(requested[1][:2]),5) if requested else 5
    for book in books:
        key=(normalize(book['title']),normalize(book['author']))
        if key in seen:
            continue
        seen.add(key)
        title=book['title']
        reason='Nhan đề: “'+title+'”.'
        if not words&tokens(title) and book['subjects']:
            reason+=' Từ khóa trong biểu ghi: '+book['subjects'][:240]+'.'
        if re.search(r'\b(?:'+TEACHING+r')\b',normalize(title)):
            reason+=' Ưu tiên tài liệu học tập vì nhan đề ghi giáo trình/bài giảng hoặc tự học.'
        if level and book['id'] in preferred:
            reason+=' Nhan đề hoặc mô tả có dấu hiệu '+('nhập môn/cơ bản' if level=='beginner' else 'nâng cao/chuyên sâu')+'; mức phù hợp dựa trên metadata này.'
        selected.append({**book,'recommendation_reason':reason})
        if len(selected)==limit:
            break
    return {'books':selected, 'query':query, 'level':level, 'level_unconfirmed':bool(level and not preferred), 'used_model':bool(planned)}
