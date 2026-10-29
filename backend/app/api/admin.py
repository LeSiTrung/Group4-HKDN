import json
import os
from datetime import date, time
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from .auth import require_admin
from ..services.knowledge import KnowledgeInput, decode_row, insert_knowledge, published_rows, today
from ..services.integrations import crawl_pages, IntegrationError
from ..services.llm_service import provider_name

router = APIRouter(prefix='/admin', tags=['administration'], dependencies=[Depends(require_admin)])


def audit(db, actor, action, target):
    db.execute('INSERT INTO audit(actor_id,action,target) VALUES (?,?,?)',(actor,action,str(target)))


@router.get('/knowledge')
def list_knowledge(request: Request):
    with request.app.state.db() as db:
        return [decode_row(x) for x in db.execute('SELECT * FROM knowledge ORDER BY id DESC')]


@router.post('/knowledge',status_code=201)
def add_knowledge(body: KnowledgeInput,request: Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        row = insert_knowledge(db,body)
        audit(db,user['id'],'knowledge.create',row['id'])
    request.app.state.vectors.invalidate()
    return row


@router.put('/knowledge/{row_id}')
def update_knowledge(row_id:int,body:KnowledgeInput,request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        if not db.execute('SELECT id FROM knowledge WHERE id=?',(row_id,)).fetchone():
            raise HTTPException(404,'Không tìm thấy nội dung.')
        row = insert_knowledge(db,body,row_id)
        audit(db,user['id'],'knowledge.update',row_id)
    request.app.state.vectors.invalidate()
    return row


@router.delete('/knowledge/{row_id}')
def remove_knowledge(row_id:int,request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        if not db.execute('DELETE FROM knowledge WHERE id=?',(row_id,)).rowcount:
            raise HTTPException(404,'Không tìm thấy nội dung.')
        audit(db,user['id'],'knowledge.delete',row_id)
    request.app.state.vectors.invalidate()
    return {'ok':True}


@router.post('/reindex')
def reindex(request:Request):
    try:
        count = request.app.state.vectors.rebuild(published_rows(request.app.state.db))
        return {'status':'ready','count':count,**request.app.state.vectors.status()}
    except Exception:
        raise HTTPException(503,'Chưa xây được chỉ mục embedding. Xem trạng thái quản trị và kiểm tra mô hình/kết nối.')


def crawl_job(state, job_id, url, max_pages):
    with state.db() as db:
        db.execute("UPDATE jobs SET status='running' WHERE id=?",(job_id,))
    try:
        pages = crawl_pages(url,max_pages)
        imported = 0
        with state.db() as db:
            for page in pages:
                if db.execute('SELECT id FROM knowledge WHERE source_url=?',(page['url'],)).fetchone():
                    continue
                body = KnowledgeInput(title=page['title'][:200],question=page['title'][:500],answer=page['text'][:12000],
                    category='imported',source_url=page['url'],source_title=page['title'][:200],checked_at=today(),status='needs_confirmation',published=False)
                insert_knowledge(db,body)
                imported += 1
            db.execute("UPDATE jobs SET status='done',imported=? WHERE id=?",(imported,job_id))
    except Exception as exc:
        error = str(exc.detail) if isinstance(exc,IntegrationError) else 'Không nhập được dữ liệu nguồn. Kiểm tra quyền truy cập, cấu trúc trang và dữ liệu.'
        with state.db() as db:
            db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",(error,job_id))


class CrawlInput(BaseModel):
    url:str = Field(min_length=10,max_length=1000)
    max_pages:int = Field(default=3,ge=1,le=10)


@router.post('/crawl',status_code=202)
def start_crawl(body:CrawlInput,request:Request,tasks:BackgroundTasks,user=Depends(require_admin)):
    with request.app.state.db() as db:
        active = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        if active>=2:
            raise HTTPException(409,'Đang có tác vụ thu thập. Vui lòng đợi hoàn tất.')
        job_id = db.execute('INSERT INTO jobs(url) VALUES (?)',(body.url,)).lastrowid
        audit(db,user['id'],'crawl.start',job_id)
    tasks.add_task(crawl_job,request.app.state,job_id,body.url,body.max_pages)
    return {'job_id':job_id}


@router.get('/jobs')
def jobs(request:Request):
    with request.app.state.db() as db:
        return [dict(x) for x in db.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 100')]


@router.get('/status')
def status(request:Request):
    with request.app.state.db() as db:
        counts = {name:db.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ('users','conversations','messages','knowledge','feedback')}
        pending = db.execute("SELECT count(*) FROM knowledge WHERE published=0").fetchone()[0]
        audit_rows = [dict(x) for x in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 30')]
    return {'counts':counts,'drafts':pending,'vectors':request.app.state.vectors.status(),
            'llm':{'provider':provider_name(),'model':os.getenv('LLM_MODEL','qwen3:4b'),'configured':provider_name()!='none'},
            'library':{'configured':bool(os.getenv('LIBRARY_LOANS_URL') and os.getenv('LIBRARY_RENEW_URL'))},
            'channels':{'messenger':bool(os.getenv('MESSENGER_PAGE_ACCESS_TOKEN')),'zalo':bool(os.getenv('ZALO_ACCESS_TOKEN'))},'audit':audit_rows}


@router.get('/users')
def users(request:Request):
    with request.app.state.db() as db:
        return [dict(x) for x in db.execute('SELECT id,email,name,role,active,created_at FROM users ORDER BY id')]


class UserState(BaseModel):
    active:bool


@router.patch('/users/{user_id}')
def user_state(user_id:int,body:UserState,request:Request,user=Depends(require_admin)):
    if user_id==user['id']:
        raise HTTPException(409,'Không thể tự khóa tài khoản quản trị.')
    with request.app.state.db() as db:
        if not db.execute('UPDATE users SET active=? WHERE id=?',(body.active,user_id)).rowcount:
            raise HTTPException(404,'Không tìm thấy người dùng.')
        if not body.active:
            db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(db,user['id'],'user.active',user_id)
    return {'ok':True}


class ScheduleInput(BaseModel):
    branch:str = Field(pattern='^[123]$')
    weekday:int = Field(ge=0,le=6)
    opens:str = ''
    closes:str = ''
    valid_from:date
    valid_until:date
    note:str = Field(default='',max_length=1000)
    verified_by:str = Field(min_length=1,max_length=100)
    source_url:str
    source_title:str = Field(default='Lịch phục vụ thư viện',min_length=1,max_length=200)
    checked_at:date
    closed:bool = False

    @model_validator(mode='after')
    def validate_schedule(self):
        KnowledgeInput.safe_url(self.source_url)
        if self.valid_from>self.valid_until or self.checked_at>today() or not self.verified_by.strip():
            raise ValueError('Khoảng ngày hoặc người xác nhận không hợp lệ.')
        if not self.closed:
            if not re_time(self.opens) or not re_time(self.closes) or self.opens>=self.closes:
                raise ValueError('Giờ mở/đóng không hợp lệ. Chọn nghỉ phục vụ nếu đóng cả ngày.')
        return self


def re_time(value):
    import re
    return bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value))


@router.get('/schedules')
def schedules(request:Request):
    with request.app.state.db() as db:
        return [dict(x) for x in db.execute('SELECT * FROM schedules ORDER BY branch,weekday,valid_from')]


@router.post('/schedules',status_code=201)
def add_schedule(body:ScheduleInput,request:Request,user=Depends(require_admin)):
    values=body.model_dump(mode='json')
    with request.app.state.db() as db:
        row_id=db.execute(f"INSERT INTO schedules({','.join(values)}) VALUES ({','.join('?' for _ in values)})",tuple(values.values())).lastrowid
        audit(db,user['id'],'schedule.create',row_id)
        return dict(db.execute('SELECT * FROM schedules WHERE id=?',(row_id,)).fetchone())


@router.delete('/schedules/{row_id}')
def delete_schedule(row_id:int,request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        if not db.execute('DELETE FROM schedules WHERE id=?',(row_id,)).rowcount:
            raise HTTPException(404,'Không tìm thấy lịch.')
        audit(db,user['id'],'schedule.delete',row_id)
    return {'ok':True}


@router.get('/renewals')
def renewal_states(request:Request):
    with request.app.state.db() as db:
        rows=[dict(r) for r in db.execute('SELECT * FROM renewals ORDER BY rowid DESC LIMIT 100')]
    for row in rows:
        row['result']=json.loads(row['result']) if row['result'] else None
    return rows


class Reconciliation(BaseModel):
    confirmation:Literal[True]
    state:Literal['succeeded','failed']
    reference:str=Field(min_length=3,max_length=500)
    due_date:date|None=None

    @model_validator(mode='after')
    def evidence_required(self):
        if not self.reference.strip() or (self.state=='succeeded' and self.due_date is None):
            raise ValueError('Cần tham chiếu đối soát và hạn trả chính thức khi thành công.')
        return self


@router.post('/renewals/{key}/reconcile')
def reconcile_renewal(key:str,body:Reconciliation,request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM renewals WHERE idempotency_key=?',(key,)).fetchone()
        if not row:
            raise HTTPException(404,'Không tìm thấy yêu cầu gia hạn.')
        if row['state'] not in ('pending','uncertain'):
            raise HTTPException(409,'Yêu cầu đã có kết quả; không được ghi đè bằng đối soát.')
        result={'status':'renewed' if body.state=='succeeded' else 'failed','loan_id':row['loan_id'],
                'origin':'manual_reconciliation','reference':body.reference.strip()}
        if body.due_date:
            result['due_date']=body.due_date.isoformat()
        db.execute('UPDATE renewals SET state=?,result=? WHERE idempotency_key=?',(body.state,json.dumps(result,ensure_ascii=False),key))
        audit(db,user['id'],'renewal.reconcile',key+':'+body.state+':'+body.reference.strip())
    return {'ok':True,'result':result}
