"""Curated metadata snapshots, distinct from live library circulation state."""
import json
import re
import os
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache, partial
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .knowledge import KnowledgeInput, today
from .rag_service import IndexBusy, normalize, STOP, NONSPACING_MARKS

_DOCUMENT_TYPES=r'(?:sach|tai lieu|(?:cuon|quyen)(?: (?:sach|tai lieu))?|luan van|luan an|khoa luan|do an|giao trinh|bai giang)'
_BOOK_PREFIX=r'(?:(?:tim|tra cuu) '+_DOCUMENT_TYPES+r'|sach)'
_FIND_DOCUMENT=r'(?:tim|tra cuu|kiem|goi y|de xuat|tu van|gioi thieu)(?: (?:cho|giup|toi|minh|ban|nhung|cac|vai|mot|so|em|0*[1-9][0-9]*))* '+_DOCUMENT_TYPES
_SEARCH_LEAD=r'(?:(?:hay|vui long|lam on) )?(?:(?:toi|minh|em|ban) )?'
_QUOTED_TEXT=r'"[^"]*"|“[^”]*”|\'[^\']*\'|‘[^’]*’|«[^»]*»'
_TOPIC_REFINEMENT=r'^(?:(?:toi|minh|em) )?(?:muon )?tap trung (?:vao|ve) (.+)$'
_SEARCH_NOISE={'tim','sach','tai','lieu','theo','quyen','cuon','tac','gia','chu','de','nguoi'}
_RESOURCE_NAMES=r'proquest|stinet|doab|doaj|co so du lieu'
# Accent folding merges "phạt" with "phát"; these library phrases are not penalties.
PENALTY_WORD = r'phat(?! (?:hanh(?! (?:vi|chinh|khach)\b)|trien)\b)'


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
    marc={key:row.pop('marc_'+key,None) for key in ('subjects','summary','audience','checked_at')}
    if marc['checked_at']:
        row['marc']=marc
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


@lru_cache(maxsize=32768)
def _similar_words(word,token):
    # Published metadata repeats token pairs; cache similarity, never rows or rankings.
    if len(token)<4 or 2*min(len(word),len(token))/(len(word)+len(token))<0.83:
        return False
    matcher=SequenceMatcher(None,word,token)
    if matcher.quick_ratio()<0.83:
        return False
    if matcher.ratio()>=0.83:
        return True
    if len(word)!=len(token):
        return False
    # A single adjacent swap has a low ratio for short terms such as HTML.
    differences=[i for i,(left,right) in enumerate(zip(word,token)) if left!=right]
    return (len(differences)==2 and differences[1]==differences[0]+1
            and word[differences[0]:differences[1]+1]==token[differences[0]:differences[1]+1][::-1])


def normalize_catalog(text):
    # C, C++ and C# are distinct catalog terms.
    text=unicodedata.normalize('NFD',text.lower().replace('đ','d')).translate(NONSPACING_MARKS)
    return ' '.join(re.sub(r'[^a-z0-9+# ]',' ',text).split())


@lru_cache(maxsize=65536)
def _normalized_metadata(text):
    # Content keys reuse Unicode work while edits and withdrawals stay visible.
    return normalize_catalog(text)


def catalog_tokens(text):
    return set(_normalized_metadata(text).split())-STOP


def _programming_languages(query):
    words=catalog_tokens(query)-_SEARCH_NOISE
    languages=words&{'c','c++','c#'}
    learning={'hoc','lap','trinh','ngon','ngu','co','can','ban','nguoi','moi','bat','dau','nang','cao','programming','language'}
    explicit=re.search(r'\b(lap trinh|ngon ngu|programming|coding|code|thuat toan|data structures)\b',normalize_catalog(query))
    return languages if languages and (words-languages<=learning or explicit) else set()


def _matches_programming_topic(row,languages):
    if not languages:
        return True
    row=dict(row)
    marc=row.get('marc',{})
    # Author initials, publication codes and MARC $c labels are not subject evidence.
    text=' '.join(filter(None,(row['title'],row['subjects'],row.get('marc_subjects'),row.get('marc_summary'),
                               marc.get('subjects'),marc.get('summary'))))
    text=normalize_catalog(re.sub(r'\$[a-z0-9]',' ',text,flags=re.I))
    if not languages<=set(text.split()):
        return False
    programming=re.search(r'\b(lap trinh|programming|coding|cau truc du lieu|data structures|thuat toan|algorithms|ngon ngu c)\b',text)
    if 'c' in languages:
        return bool(programming)
    return bool(programming or re.search(r'\b(cong nghe thong tin|tin hoc|computer science|information technology|software|phan mem|windows forms?|asp net|visual studio)\b',text))


@lru_cache(maxsize=4)
def _discovery_rows(db_factory,kind,revision):
    # Revision keys invalidate this public-only projection after committed edits.
    with db_factory() as db:
        return db.execute('SELECT * FROM books_discovery WHERE published=1'+(' AND kind=?' if kind!='all' else ''),(() if kind=='all' else (kind,))).fetchall()


def search_local(db_factory,query,kind='all',field='all',*,fuzzy=True):
    if field not in ('all','title','author'):
        raise ValueError('Unsupported catalog field')
    with db_factory() as db:
        revision=db.execute('SELECT value FROM catalog_revision WHERE id=1').fetchone()[0]
    rows=_discovery_rows(db_factory,kind,revision)
    normalized=normalize_catalog(query)
    languages=_programming_languages(query) if field!='author' else set()
    if not normalized:
        return []
    if field!='all':
        pattern=re.compile(r'(?<![\w+#])'+re.escape(normalized)+r'(?![\w+#])')
        matched=[]
        for row in rows:
            values=row[field].split(';') if field=='author' else [row[field]]
            values=[_normalized_metadata(value) for value in values]
            if any(pattern.search(value) for value in values) and _matches_programming_topic(row,languages):
                matched.append((item(row),normalized in values))
        matched.sort(key=lambda pair:(not pair[1],pair[0]['id']))
        return [row for row,_ in matched]
    words=catalog_tokens(query)-_SEARCH_NOISE
    required={word for word in words if word=='c' or '+' in word or '#' in word}
    if not words:
        return [item(row) for row in rows if _normalized_metadata(row['title'])==normalized]
    fuzzy_matchers={word:partial(_similar_words,word) for word in words if len(word)>=4} if fuzzy else {}
    ranked=[]
    complete=[]
    for row in rows:
        text=_normalized_metadata(' '.join(row[k] or '' for k in
                                           ('title','author','year','subjects','description','marc_subjects','marc_summary')))
        corpus=set(text.split())
        if not required<=corpus:
            continue
        if not _matches_programming_topic(row,languages):
            continue
        matched=len(words&corpus)
        for word,matches in fuzzy_matchers.items():
            if word not in corpus and any(map(matches,corpus)):
                matched+=1
        coverage=matched/len(words)
        if coverage<0.6:
            continue
        title_hits=len(words&catalog_tokens(row['title']))
        author_hits=len(words&catalog_tokens(row['author']))
        ranked.append((item(row),coverage+title_hits*0.15+author_hits*0.1))
        if coverage==1:
            complete.append(ranked[-1])
    ranked=complete or ranked
    ranked.sort(key=lambda pair:(_normalized_metadata(pair[0]['title'])!=normalized,-pair[1],pair[0]['id']))
    return [r for r,_ in ranked]


def public_book(db_factory,row_id):
    with db_factory() as db:
        row=db.execute('SELECT * FROM books_discovery WHERE id=? AND published=1',(row_id,)).fetchone()
    return item(row) if row else None


def book_documents(rows):
    return [{'id':r['id'],'question':r['title'],
             'aliases':[r['author'],r['subjects']]+([r['marc']['subjects']] if r.get('marc',{}).get('subjects') else []),
             'answer':'\n'.join(filter(None,(r['description'],r.get('marc',{}).get('summary')))) or r['title']} for r in rows]


def published_book_rows(db_factory):
    with db_factory() as db:
        return [item(row) for row in db.execute('SELECT * FROM books_discovery WHERE published=1 ORDER BY id')]


def search_books(state,query,kind='all',field='all'):
    return search_books_with_status(state,query,kind,field)[0]


def search_books_with_status(state,query,kind='all',field='all'):
    matched=search_local(state.db,query,kind,field,fuzzy=False)
    if field=='all':
        phrase=re.compile(r'(?<![\w+#])'+re.escape(normalize_catalog(query))+r'(?![\w+#])')
        precise=[b for b in matched if phrase.search(_normalized_metadata(' '.join(
            (b['title'],b['subjects'],b.get('marc',{}).get('subjects',''),b.get('marc',{}).get('summary','')))))]
        matched=precise or search_local(state.db,query,kind,field)
    # Single-term identifiers need a lexical match, not an unrelated vector suggestion.
    words=catalog_tokens(query)-_SEARCH_NOISE
    languages=_programming_languages(query)
    required={word for word in words if word=='c' or '+' in word or '#' in word}
    if field!='all' or matched or len(words)<2 or state.settings.testing or os.getenv('ENABLE_VECTORS','true').lower()!='true':
        return matched,None
    try:
        if len(query.encode('utf-8'))>384:
            return [],None
    except UnicodeEncodeError:
        return [],None
    def load_documents():
        return book_documents(published_book_rows(state.db))
    status=state.vectors.prepare_books(load_documents)
    if status!='ready':
        return [],status
    rows=published_book_rows(state.db)
    documents=book_documents(rows)
    if not documents:
        return [],None
    try:
        # All published rows already define the index; a huge MatchAny filter is redundant.
        source_ids=None if kind=='all' else {row['id'] for row in rows if row['kind']==kind}
        hits=state.vectors.search(query,documents,namespace='books',source_ids=source_ids,ready_only=True)
    except IndexBusy:
        status=state.vectors.prepare_books(load_documents)
        return [],'busy' if status=='ready' else status
    except Exception:
        return [],'unavailable'
    results=[]
    for row,_ in hits:
        current=public_book(state.db,row['id'])
        if current and (kind=='all' or current['kind']==kind):
            marc=current.get('marc',{})
            corpus=set(_normalized_metadata(' '.join((current['title'],current['subjects'],current['description'],
                                                      marc.get('subjects',''),marc.get('summary','')))).split())
            if not required<=corpus:
                continue
            if not _matches_programming_topic(current,languages):
                continue
            # shortcut: synonyms without lexical evidence are omitted until semantic precision is validated.
            if words&corpus or any(len(word)>=4 and any(len(token)>=4 and _similar_words(word,token) for token in corpus) for word in words):
                results.append(current)
    return results,None


def is_borrowing_procedure(question):
    q=normalize(unquoted_text(question))
    borrowing=re.search(r'\bmuon '+_DOCUMENT_TYPES+r'\b',q)
    if not borrowing:
        return False
    lookup=re.search(r'\b'+_FIND_DOCUMENT+r'\b',q)
    if lookup:
        # A completed lookup can be context for a new question about the desk.
        previous_lookup = re.search(r'\b(?:da|sau khi) $', q[:lookup.start()])
        desk = re.search(r'\b(?:tai|o|ra|den) quay\b', q[borrowing.end():])
        if not (lookup.start() < borrowing.start() and previous_lookup and desk):
            return False
    return bool(re.search(r'\b(chuan bi|thu tuc|quy trinh|dieu kien|can (?:lam|mang|the)|lam gi|giay to|the sinh vien|cach|lam the nao|lam sao|(?:nhu )?the nao|ra sao|huong dan|online|truc tuyen|opac)\b',q))


def unquoted_text(question):
    # Quoted titles are data, even when they contain instructional phrases.
    return re.sub(_QUOTED_TEXT,'chủ đề',question)


def search_guidance(question):
    """Resolve how-to lookup questions to reviewed FAQ topics, not book titles."""
    if is_borrowing_procedure(question):
        return None
    q=normalize(unquoted_text(question))
    quoted=re.split(r'["“\'‘«]',question,maxsplit=1)
    if len(quoted)>1 and re.fullmatch(_SEARCH_LEAD+_FIND_DOCUMENT,normalize(quoted[0])):
        return None
    if 'opac' not in q.split() and re.search(r'\b(?:'+_RESOURCE_NAMES+r')\b',q):
        return None
    if 'opac' in q.split() and re.search(r'\bra (?:so )?0\b',q):
        return 'OPAC không có kết quả thì làm sao?'
    lookup=re.search(r'\b(tim|kiem|tra cuu|truy cap|tai (?:ebook|sach|tai lieu)|(?:su dung|dung) opac|opac (?:su dung|dung))\b',q)
    if not lookup or not re.search(r'\b('+_DOCUMENT_TYPES+r'|opac|ebook|thu vien)\b',q):
        return None
    how=re.search(r'\b(huong dan|hdsd|cach|lam the nao|lam sao|quy trinh|cac buoc|chi (?:cho )?(?:toi|minh|em)|khong biet)\b',q)
    ending=re.search(r'\b((?:nhu )?the nao|ra sao|bang cach nao|o dau|(?:can|phai) lam gi)(?: (?:a|vay|nhi|khong))?$',q)
    missing=re.search(r'\b(khong (?:co|ra) ket qua|khong tim thay)\b',q)
    # A leading search command may contain a title such as "Hướng dẫn lập trình".
    if not (how and how.start()<lookup.start()) and not ending and not missing:
        return None
    if missing:
        return 'OPAC không có kết quả thì làm sao?'
    if re.search(r'\b(ebook|(?:tai lieu|sach) (?:so|dien tu))\b',q):
        return 'Tìm tài liệu số và tải ebook thế nào?'
    if re.search(r'\b(nang cao|and|or|not)\b',q):
        return 'Dùng tìm kiếm nâng cao AND OR NOT thế nào?'
    if re.search(r'\b(tac gia|nhan de|theo ten|nha xuat ban|nam xuat ban)\b',q):
        return 'Tìm theo tác giả hoặc nhan đề như thế nào?'
    if re.search(r'\bsach (?:truyen thong|giay|in)\b',q):
        return 'Tìm sách truyền thống trên OPAC thế nào?'
    return 'Hướng dẫn tra cứu OPAC'


def is_book_request(question):
    q=normalize(unquoted_text(question))
    if search_guidance(question) or is_borrowing_procedure(question) or (re.search(r'\bmuon '+_DOCUMENT_TYPES+r'\b',q) and re.search(r'\b(bao lau|bao nhieu ngay|han tra|thoi han)\b',q)):
        return False
    if re.fullmatch(r'(?:tim|tra cuu) '+_DOCUMENT_TYPES+r'(?: (?:(?:va|hoac) )?'+_DOCUMENT_TYPES+r')*',q):
        return False
    if re.search(r'\bco (sach|cuon|quyen)\b',q) and re.search(r'\b(qua han|phi|'+PENALTY_WORD+r'|han tra|gia han)\b',q):
        return False
    if structured_book_query(question):
        return True
    explicit=re.match(r'^'+_SEARCH_LEAD+_FIND_DOCUMENT+r'\b',q)
    if not explicit and re.search(r'\b(?:dem|mang) sach ve\b',q):
        return False
    if re.search(r'\b(?:'+_RESOURCE_NAMES+r')\b',q) and re.search(r'\b(nguon|truy cap|huong dan|khac nhau|dang lai|ban quyen)\b',q):
        return False
    return bool(re.search(r'\b('+_FIND_DOCUMENT+r'|co (?:sach|cuon|quyen) .+|sach ve|sach cua|sach tuong tu|sach danh cho|(?:nen|muon|can) (?:doc )?'+_DOCUMENT_TYPES+r'|'+_DOCUMENT_TYPES+r' (?:nao|gi))\b',q)) and (bool(explicit) or not any(x in q for x in ('huong dan','cach tim','lam sao','nhu the nao','o dau','vao dau')))


_BOOK_ATTRIBUTES=(
        ('availability',r'con ban|con sach|co san|con khong|tinh trang|con muon|muon duoc|bao nhieu ban|so ban'),
        ('isbn',r'isbn'),('shelf',r'o ke|ke nao|xep gia|vi tri(?: ke)?'),
        ('publisher',r'nha xuat ban'),('author',r'tac gia|ai viet|nguoi viet'),
        ('year',r'(?<!nha )xuat ban|nam nao'),
        ('summary',r'noi ve gi|tom tat|noi dung (?:la )?gi'),
        ('audience',r'danh cho ai|doi tuong doc'),
)


def book_attributes(question):
    q=normalize(question)
    return [attribute for attribute,pattern in _BOOK_ATTRIBUTES if re.search(r'\b(?:'+pattern+r')\b',q)]


def book_attribute(question):
    return next(iter(book_attributes(question)),None)


def _attribute_phrase(question):
    q=normalize(question)
    if not book_attributes(q):
        return False
    q=re.sub(r'^(?:(?:vui long|lam on) )?(?:ban )?(?:co the )?cho (?:toi|minh|em) biet\b','',q).strip()
    q=re.sub(r'\s+(?:duoc )?khong(?: a)?$','',q)
    for _,pattern in _BOOK_ATTRIBUTES:
        q=re.sub(r'\b(?:'+pattern+r')\b',' ',q)
    q=re.sub(r'\b(?:cho (?:toi|minh|em) biet|o dau|va|cung|voi|cua|tai lieu|cuon sach|cuon|quyen|sach|no|nay|do|ay|nam|la|ai|gi|nao|vay|the|con|nhi|a)\b',' ',q)
    return not q.split()


def book_reference(question):
    if search_guidance(question) or is_borrowing_procedure(question):
        return False
    q=normalize(unquoted_text(question))
    return bool(book_attribute(q) and (
        re.search(r'\b(?:(?:cuon|quyen|sach|tai lieu)(?: sach)? (?:nay|do|ay)|no)\b',q) or
        _attribute_phrase(q)))


def book_position(question):
    match=re.search(r'\b(?:cuon|quyen|sach|tai lieu)(?: sach)? (?:thu (nhat|mot|hai|ba|tu|bon|nam|\d{1,3})|(dau tien))\b',normalize(unquoted_text(question)))
    if not match:
        return None
    value=match[1] or match[2]
    return int(value) if value.isdigit() else {'dau tien':1,'nhat':1,'mot':1,'hai':2,'ba':3,'tu':4,'bon':4,'nam':5}[value]


def book_followup(question):
    if unquoted_text(question)!=question:
        return False
    q=normalize(question)
    return bool(book_position(question) is not None or book_reference(question) or re.search(r'^(co (?:cuon|quyen|sach)|cuon nao|sach nay|sach do|cuon nay|cuon do|tai lieu (?:nay|do)|noi ve gi|tom tat|noi dung|doi tuong doc|con khong|con ban|con sach|con muon|co san|danh cho|cho nguoi moi|nguoi moi|nang cao|tuong tu|tac gia|ai viet|nam xuat ban|xuat ban|isbn|o ke|co bao nhieu ban)',q) or re.fullmatch(_TOPIC_REFINEMENT,q)) and not any(x in q for x in ('huong dan','cach tim','nhu the nao'))


def author_query(question):
    match=re.fullmatch(_BOOK_PREFIX+r' (?:cua(?: tac gia)?|(?:theo )?tac gia) (.+)',normalize_catalog(question))
    return match[1] if match else None


def structured_book_query(question):
    quoted=re.search(r'('+_QUOTED_TEXT+r')\s*[?.!]?\s*$',question)
    if quoted and re.fullmatch(_SEARCH_LEAD+_FIND_DOCUMENT,normalize(question[:quoted.start()])):
        title=normalize_catalog(quoted[1][1:-1])
        if title:
            return 'title',title
    match=re.fullmatch(_SEARCH_LEAD+r'(?:tim|tra cuu|kiem)(?: '+_DOCUMENT_TYPES+r')? theo (nhan de|ten|tac gia) (.+)',normalize_catalog(question))
    if match:
        return ('author' if match[1]=='tac gia' else 'title'),match[2]
    viewed=re.fullmatch(r'(?:(?:em|toi|minh) )?dang (?:xem|doc) (?:cuon(?: sach)?|quyen(?: sach)?|sach|tai lieu) (.+?) (?:trong|tren) danh muc(?: thu vien)?',normalize_catalog(question))
    if viewed:
        return 'title',viewed[1]
    return None


def direct_document_question(question):
    quoted=re.search(_QUOTED_TEXT,question)
    if not quoted:
        return None
    prefix=normalize(question[:quoted.start()])
    suffix=normalize(question[quoted.end():])
    title=normalize_catalog(quoted[0][1:-1])
    if not title:
        return None
    attributes=book_attributes(prefix+' '+suffix)
    if attributes and _attribute_phrase(prefix+' '+suffix):
        return attributes[0],title
    if re.fullmatch(r'tac gia(?: cua)?(?: tai lieu| sach| cuon sach)?',prefix) and suffix in ('','la ai'):
        return 'author',title
    if re.fullmatch(r'nam xuat ban(?: cua)?(?: tai lieu| sach| cuon sach)?',prefix) and suffix in ('','la gi'):
        return 'year',title
    if not suffix:
        if re.fullmatch(r'(?:tom tat|noi dung(?: cua)?)(?: tai lieu| sach| cuon sach)?',prefix):
            return 'summary',title
        if re.fullmatch(r'doi tuong doc(?: cua)?(?: tai lieu| sach| cuon sach)?',prefix):
            return 'audience',title
    if prefix in ('','tai lieu','sach','cuon sach'):
        if suffix in ('do ai viet','cua tac gia nao','tac gia la ai'):
            return 'author',title
        if suffix in ('xuat ban nam nao','nam xuat ban la gi'):
            return 'year',title
        if suffix in ('noi ve gi','co noi dung gi','noi dung la gi'):
            return 'summary',title
        if suffix=='danh cho ai':
            return 'audience',title
    return None


def explicit_metadata_lookups(question):
    # shortcut: recover separate author/year clauses only; broaden after evaluating mixed intents.
    boundaries=[0]
    for match in re.finditer(_QUOTED_TEXT+r'|(?P<end>[.!?;](?=\s|$)|\n)',question):
        if match.lastgroup=='end':
            boundaries.append(match.end())
    boundaries.append(len(question))
    lookups={}
    for start,end in zip(boundaries,boundaries[1:]):
        clause=re.sub(r'^\s*(?:sau đó|sau do)\s+','',question[start:end],flags=re.I).strip()
        direct=direct_document_question(clause)
        attributes=book_attributes(unquoted_text(clause))
        if direct and attributes and set(attributes)<={'author','year'}:
            key=('title',direct[1])
        else:
            editor=re.fullmatch(r'(?:hay )?cho (?:toi|minh|em) (?:biet )?tac gia va nam(?: xuat ban)? cua (?:cuon(?: sach)?|sach|tai lieu) do (.+?) chu bien',normalize_catalog(clause))
            if not editor:
                continue
            key=('author',editor[1]+' chu bien')
            attributes=['author','year']
        if len(key[1])<=200:
            lookups.setdefault(key,set()).update(attributes)
    return lookups


def search_correction(question):
    prefix=re.match(r'^\s*(?:ý tôi là|y toi la|ý mình là|y minh la|tôi hỏi nhầm|toi hoi nham|mình hỏi nhầm|minh hoi nham|không,|khong,)\s*[,;:]?\s*',question,re.I)
    corrected=question[prefix.end():] if prefix else question
    return corrected if prefix and is_book_request(corrected) else question


def book_query(question):
    question=search_correction(question)
    structured=structured_book_query(question)
    if structured:
        return structured[1]
    author=author_query(question)
    if author:
        return author
    if re.match(_SEARCH_LEAD+_FIND_DOCUMENT,normalize(question)):
        question=re.split(r'[,;]\s*(?:và |va )?(?=(?:tóm tắt|tom tat)\b)',question,maxsplit=1,flags=re.I)[0]
    q=normalize_catalog(question)
    if re.match(_SEARCH_LEAD+_FIND_DOCUMENT,normalize(question)):
        q=re.split(r'\b(?:giup (?:toi|minh|em) (?:xac dinh|cho biet)|ban ghi (?:thu vien )?ghi)\b',q,maxsplit=1)[0]
        q=re.sub(r'\b(?:hinh nhu ten co chu|bang|voi|chu bien)\b',' ',q)
    q=re.sub(r'^(?:hay|vui long|lam on) ','',q)
    interrogative=bool(re.match(r'^co '+_DOCUMENT_TYPES+r'\b',q))
    wrapper=r'(?:(?:toi|minh|em|ban) )?(?:'+_FIND_DOCUMENT+r'|(?:(?:co|(?:nen|muon|can)(?: doc)?) )?'+_DOCUMENT_TYPES+r'(?: (?:nao|gi))?)'
    q=re.sub(r'^'+wrapper+r'\b','',q,count=1).strip()
    q=re.sub(r'^(?:ve|tuong tu|theo chu de|theo ten)\b','',q)
    q=re.sub(r'\bco '+_DOCUMENT_TYPES+r' (?:nao|gi)\b',' ',q)
    q=re.sub(r'\b(?:nen|can) doc '+_DOCUMENT_TYPES+r'(?: (?:gi|nao))?$','',q)
    q=re.split(r'\b(?:con muon|muon duoc|con ban|con sach|co san|bao nhieu ban|tinh trang)\b',q,maxsplit=1)[0]
    if interrogative:
        q=re.sub(r'^giup (?:toi|minh|em|ban) (?:hieu )?','',q)
        q=re.sub(r'\bkhong$','',q)
    if re.match(_SEARCH_LEAD+_FIND_DOCUMENT,normalize(question)):
        trimmed=re.sub(r'\b(?:giup (?:toi|minh|em)(?: voi| nhe)?|tren opac|tai thu vien)$','',q).strip()
        q=trimmed or q
    return ' '.join(q.split())


def smart_catalog_search(state, question, kind):
    from .recommendations import TEACHING, recommendation_topic

    question=search_correction(question)
    guidance=bool(search_guidance(question) or is_borrowing_procedure(question))
    field,query='all',''
    learning_goal=False
    if not guidance:
        structured=structured_book_query(question)
        author=author_query(question) if not structured else None
        field,query=structured or (('author',author) if author else ('all',book_query(question)))
        learning=re.match(r'^(?:(?:toi|minh|em) )?((?:muon hoc|can hoc|moi hoc|tu hoc|dang hoc)\b.*)$',normalize_catalog(question))
        if field=='all' and learning:
            query=recommendation_topic(learning[1])[0]
            learning_goal=bool(query)
        elif field=='all' and query==normalize_catalog(question):
            query=question
    rows,semantic_status=search_books_with_status(state,query,kind,field) if query else ([],None)
    if learning_goal:
        teaching=re.compile(r'\b(?:'+TEACHING+r'|cam nang|so tay|handbook)\b')
        rows.sort(key=lambda row:not teaching.search(normalize(row['title'])))
    if field=='all' and rows:
        phrase=re.compile(r'(?<![\w+#])'+re.escape(normalize_catalog(query))+r'(?![\w+#])')
        for row in rows:
            marc=row.get('marc',{})
            match=next((key for key in ('subjects','summary') if marc.get(key) and
                        phrase.search(_normalized_metadata(marc[key]))),None)
            if match:
                row['marc_match']=match
    titles=[]
    for row in rows:
        title=row['title']
        if len(title)<=200 and title not in titles:
            titles.append(title)
            if len(titles)==3:
                break
    keywords={}
    normalized_query=normalize_catalog(query)
    for row in rows[:3]:
        for term in (row.get('marc',{}).get('subjects','')+';'+row['subjects']).split(';'):
            term=re.sub(r'^(?:TV|TA)\s+','',term.strip())
            key=normalize_catalog(term)
            if len(key.split())>=2 and len(term)<=80 and key not in (normalized_query,'tieng viet','tieng anh'):
                keywords.setdefault(key,term)
    return rows, {'interpretation':{'field':field,'query':query},'guidance':guidance,
                  'learning_goal':learning_goal,'suggested_titles':titles,'suggested_keywords':list(keywords.values())[:3],
                  **({'semantic_status':semantic_status} if semantic_status else {})}


def contextual_question(question,history):
    q=normalize(question)
    if search_guidance(question):
        return question
    new_topic=re.search(r'^co (?:cuon|quyen|sach) nao (?:.*\bve |hoc (?!co ban\b|nhap mon\b|nang cao\b|tu dau\b|khong\b))\S+',q)
    if is_book_request(question) and (not re.search(r'^co (?:cuon|quyen|sach) (?:nao|do|nay)\b',q) or new_topic):
        return question
    if re.fullmatch(r'(?:co so|cs)\s*[123]',q):
        previous=next((m['content'] for m in reversed(history or []) if m['role']=='user'),None)
        if previous and any(x in normalize(previous) for x in ('mo cua','gio phuc vu','lich phuc vu')):
            return previous+' '+question
    if not book_followup(question):
        return question
    attribute=book_attribute(question)
    refinement=re.fullmatch(_TOPIC_REFINEMENT,q)
    for turn in reversed(history or []):
        if turn.get('context_query'):
            if refinement:
                return 'Gợi ý sách '+refinement[1]
            context=turn['context_query']
            return (context if is_book_request(context) else 'Tìm sách về '+context)+('' if attribute else ' '+question)
        if turn['role']=='user':
            direct=direct_document_question(turn['content'])
            if direct:
                if refinement:
                    return 'Gợi ý sách '+refinement[1]
                return ('Tìm theo nhan đề ' if attribute else 'Tìm sách ')+direct[1]+('' if attribute else ' '+question)
            if is_book_request(turn['content']):
                if refinement:
                    return 'Gợi ý sách '+refinement[1]
                return turn['content']+('' if attribute else ' '+question)
            if not book_followup(turn['content']):
                break
    return question


def selected_title(history):
    for turn in reversed(history or []):
        if turn['role']!='user':
            continue
        direct=direct_document_question(turn['content'])
        if direct:
            return direct[1]
        if is_book_request(turn['content']):
            structured=structured_book_query(turn['content'])
            if structured:
                return structured[1] if structured[0]=='title' else ''
            match=re.fullmatch(_BOOK_PREFIX+r' (.+)',normalize_catalog(turn['content']))
            return match[1] if match else ''
        if not book_followup(turn['content']):
            break
    return ''
