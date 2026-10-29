import json
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal


def today():
    return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()


class KnowledgeInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=40)
    answer: str = Field(min_length=1, max_length=12000)
    category: str = Field(min_length=1, max_length=50)
    source_url: str = Field(max_length=1000)
    source_title: str = Field(min_length=1, max_length=200)
    checked_at: date
    status: Literal['reviewed_public', 'needs_confirmation', 'verified']
    published: bool = False
    valid_from: date | None = None
    valid_until: date | None = None
    verified_by: str | None = Field(default=None, max_length=100)

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, v):
        p = urlparse(v)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
            raise ValueError('Nguồn phải là URL HTTPS không chứa thông tin đăng nhập.')
        return v

    @field_validator('title', 'question', 'answer', 'source_title')
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError('Nội dung không được để trống.')
        return v.strip()

    @field_validator('aliases', 'keywords')
    @classmethod
    def bounded_strings(cls, v):
        if any(not x.strip() or len(x)>500 for x in v):
            raise ValueError('Từ khóa/cách hỏi phải có nội dung và không quá 500 ký tự.')
        return v

    @model_validator(mode='after')
    def coherent(self):
        if self.checked_at > today():
            raise ValueError('Ngày kiểm tra không được ở tương lai.')
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError('Khoảng hiệu lực không hợp lệ.')
        if self.status == 'verified' and not (self.verified_by or '').strip():
            raise ValueError('Cần ghi người xác nhận nghiệp vụ.')
        if self.status == 'verified' and self.category in ('hours','fees','policy') and not (self.valid_from and self.valid_until):
            raise ValueError('Quy định hiện hành cần khoảng ngày hiệu lực.')
        return self


def decode_row(row):
    row = dict(row)
    for k in ('aliases', 'keywords'):
        row[k] = json.loads(row[k])
    row['published'] = bool(row['published'])
    return row


def insert_knowledge(db, body, row_id=None):
    values = body.model_dump(mode='json')
    for k in ('aliases','keywords'):
        values[k] = json.dumps(values[k], ensure_ascii=False)
    if row_id is None:
        columns = ','.join(values)
        cursor = db.execute(f"INSERT INTO knowledge({columns}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
        row_id = cursor.lastrowid
    else:
        db.execute(f"UPDATE knowledge SET {','.join(k+'=?' for k in values)},updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?", (*values.values(), row_id))
    return decode_row(db.execute('SELECT * FROM knowledge WHERE id=?', (row_id,)).fetchone())


def published_rows(db_factory):
    now = today().isoformat()
    with db_factory() as db:
        rows = db.execute('SELECT * FROM knowledge WHERE published=1 AND (valid_from IS NULL OR valid_from<=?) AND (valid_until IS NULL OR valid_until>=?) ORDER BY id', (now,now)).fetchall()
    return [decode_row(x) for x in rows]


def seed(db_factory, seed_path):
    with db_factory() as db:
        # Deleting/withdrawing all content must not resurrect it on restart.
        db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        if db.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
            return
        for item in json.loads(seed_path.read_text(encoding='utf-8')):
            body = KnowledgeInput(title=item['question'], source_title='Thư viện UTH', checked_at='2026-10-28', published=True, **item)
            insert_knowledge(db, body)
        db.execute("INSERT INTO meta VALUES ('seeded','1')")
