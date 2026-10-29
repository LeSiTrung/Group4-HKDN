import json
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal
from urllib.parse import urlencode
from .auth import require_user,ensure_current_account
from ..services.integrations import IntegrationError, search_catalog, library_loans, library_renew
from ..services.catalog import search_books

router = APIRouter(tags=['library'])


@router.get('/catalog')
def catalog(request:Request,q: str = Query(min_length=1,max_length=200),kind:Literal['all','books','digital']='all',
            source:Literal['auto','local','opac']='auto',page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=50)):
    q=q.strip()
    if not q:
        raise HTTPException(422,'Vui lòng nhập từ khóa.')
    if source!='opac':
        rows=search_books(request.app.state,q,kind)
        if rows or source=='local':
            start=(page-1)*page_size
            return {'items':rows[start:start+page_size],'total':len(rows),'page':page,'page_size':page_size,'source':'local',
                    'search_url':'https://opacthuvien.ut.edu.vn/opac/',
                    'warning':'Kết quả từ metadata đã rà soát, kèm ngày cập nhật. Không phải số bản rỗi hoặc tình trạng lưu thông hiện tại.'}
    if page!=1:
        raise HTTPException(422,'Bộ nối OPAC hiện chỉ trả trang đầu. Hãy mở trang mục lục gốc để xem trang tiếp theo.')
    try:
        return search_catalog(q,kind)
    except IntegrationError as exc:
        search_url = 'https://opacthuvien.ut.edu.vn/opac/'
        search_url += 'Oshow.aspx?'+urlencode({'rdSearchOption':{'all':0,'books':1,'digital':-4}[kind],'txtSearch':q})
        return JSONResponse({'detail':exc.detail,'search_url':search_url},exc.status_code)


class LibraryAccess(BaseModel):
    access_token:str = Field(min_length=1,max_length=4096)


class Renewal(LibraryAccess):
    loan_id:str = Field(min_length=1,max_length=128)
    idempotency_key:str = Field(min_length=12,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')
    confirmation:Literal[True]


@router.post('/library/loans')
def loans(body:LibraryAccess,user=Depends(require_user)):
    return library_loans(body.access_token)


@router.post('/library/renew')
def renew(body:Renewal,request:Request,user=Depends(require_user)):
    if not os.getenv('LIBRARY_RENEW_URL'):
        raise HTTPException(503,'Chưa có kết nối gia hạn do thư viện cấp phép. Chưa gửi giao dịch.')
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        row=db.execute('SELECT * FROM renewals WHERE idempotency_key=?',(body.idempotency_key,)).fetchone()
        if row:
            if row['user_id']!=user['id'] or row['loan_id']!=body.loan_id:
                raise HTTPException(409,'Mã yêu cầu đã được dùng cho giao dịch khác.')
            if row['state']=='succeeded':
                return json.loads(row['result'])
            raise HTTPException(409,'Yêu cầu đã được ghi nhận. Cần đối soát trạng thái trước khi gửi lại.')
        if db.execute("SELECT 1 FROM renewals WHERE user_id=? AND loan_id=? AND state IN ('pending','uncertain')",(user['id'],body.loan_id)).fetchone():
            raise HTTPException(409,'Có yêu cầu chưa xác định kết quả cho tài liệu này. Vui lòng liên hệ đối soát.')
        db.execute("INSERT INTO renewals VALUES (?,?,?,'pending',NULL)",(body.idempotency_key,user['id'],body.loan_id))
    try:
        result=library_renew(body.access_token,body.loan_id,body.idempotency_key)
    except Exception as exc:
        uncertain = getattr(exc,'uncertain',True)
        with request.app.state.db() as db:
            ensure_current_account(db,user)
            changed=db.execute("UPDATE renewals SET state=? WHERE idempotency_key=? AND user_id=? AND state='pending'",('uncertain' if uncertain else 'failed',body.idempotency_key,user['id'])).rowcount
            if not changed:
                row=db.execute('SELECT * FROM renewals WHERE idempotency_key=? AND user_id=?',(body.idempotency_key,user['id'])).fetchone()
                if row and row['state']=='succeeded':
                    return json.loads(row['result'])
                raise HTTPException(409,'Yêu cầu đã được đối soát. Hãy kiểm tra kết quả trước khi gửi lại.')
        if isinstance(exc,IntegrationError):
            raise
        raise HTTPException(409,'Chưa xác định kết quả. Không gửi lại trước khi đối soát với thư viện.')
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        db.execute("UPDATE renewals SET state='succeeded',result=? WHERE idempotency_key=? AND user_id=? AND state='pending'",(json.dumps(result,ensure_ascii=False),body.idempotency_key,user['id']))
        row=db.execute('SELECT * FROM renewals WHERE idempotency_key=? AND user_id=?',(body.idempotency_key,user['id'])).fetchone()
        if row and row['state']=='succeeded':
            return json.loads(row['result'])
    raise HTTPException(409,'Yêu cầu đã được đối soát. Hãy kiểm tra kết quả trước khi gửi lại.')
