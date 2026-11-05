import sqlite3
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Path,Query,Request
from pydantic import BaseModel,Field,model_validator
from .auth import require_admin
from .admin import audit
from ..services.catalog import BookInput,item,save_book,public_book,search_local

router=APIRouter(tags=['curated catalog'])


@router.get('/admin/books',dependencies=[Depends(require_admin)])
def list_books(request:Request,q:str=Query('',max_length=500),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=50)):
    with request.app.state.db() as db:
        db.create_function('casefold',1,str.casefold,deterministic=True)
        where=" WHERE instr(casefold(title||' '||author||' '||subjects),?)>0" if q else ''
        params=(q.casefold(),) if q else ()
        total=db.execute('SELECT COUNT(*) FROM books'+where,params).fetchone()[0]
        page=min(page,max(1,(total+page_size-1)//page_size))
        rows=db.execute('SELECT * FROM books'+where+' ORDER BY id DESC LIMIT ? OFFSET ?',(*params,page_size,(page-1)*page_size))
        return {'items':[item(r) for r in rows],'total':total,'page':page,'page_size':page_size}


@router.post('/admin/books',status_code=201)
def create_book(body:BookInput,request:Request,user=Depends(require_admin)):
    try:
        with request.app.state.db() as db:
            row=save_book(db,body)
            audit(db,user['id'],'book.create',row['id'])
    except sqlite3.IntegrityError:
        raise HTTPException(409,'Nguồn biểu ghi đã tồn tại; hãy sửa bản ghi hiện có.')
    request.app.state.vectors.invalidate()
    return row


@router.put('/admin/books/{row_id}')
def update_book(row_id:Annotated[int,Path(gt=0,le=9223372036854775807)],body:BookInput,request:Request,user=Depends(require_admin)):
    try:
        with request.app.state.db() as db:
            if not db.execute('SELECT 1 FROM books WHERE id=?',(row_id,)).fetchone():
                raise HTTPException(404,'Không tìm thấy biểu ghi.')
            row=save_book(db,body,row_id)
            audit(db,user['id'],'book.update',row_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409,'Nguồn biểu ghi đã thuộc bản ghi khác.')
    request.app.state.vectors.invalidate()
    return row


@router.delete('/admin/books/{row_id}')
def delete_book(row_id:Annotated[int,Path(gt=0,le=9223372036854775807)],request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        if not db.execute('DELETE FROM books WHERE id=?',(row_id,)).rowcount:
            raise HTTPException(404,'Không tìm thấy biểu ghi.')
        audit(db,user['id'],'book.delete',row_id)
    request.app.state.vectors.invalidate()
    return {'ok':True}


class ImportBooks(BaseModel):
    items:list[BookInput]=Field(min_length=1,max_length=200)

    @model_validator(mode='after')
    def unique_sources(self):
        if len({b.source_url for b in self.items})!=len(self.items):
            raise ValueError('Tệp nhập có URL biểu ghi trùng lặp.')
        return self


@router.post('/admin/books/import',status_code=201)
def import_books(body:ImportBooks,request:Request,user=Depends(require_admin)):
    with request.app.state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        for book in body.items:
            existing=db.execute('SELECT id FROM books WHERE source_url=?',(book.source_url,)).fetchone()
            row=save_book(db,book,existing['id'] if existing else None)
            audit(db,user['id'],'book.import',row['id'])
    request.app.state.vectors.invalidate()
    return {'imported':len(body.items)}


@router.get('/catalog/{row_id}')
def detail(row_id:Annotated[int,Path(gt=0,le=9223372036854775807)],request:Request):
    row=public_book(request.app.state.db,row_id)
    if not row:
        raise HTTPException(404,'Không tìm thấy biểu ghi đã công bố.')
    author=next((value.strip() for value in row['author'].split(';') if value.strip()),'')
    query=author or row['subjects'] or row['title']
    related=[r for r in search_local(request.app.state.db,query,field='author' if author else 'all') if r['id']!=row_id][:3]
    return {**row,'related':related,'warning':'Thông tin có nguồn và ngày đối chiếu. Hãy kiểm tra tình trạng còn sách tại thư viện trước khi đến.'}
