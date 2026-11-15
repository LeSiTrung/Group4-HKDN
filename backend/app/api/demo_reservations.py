from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from .auth import ensure_current_account, require_user
from ..services.knowledge import today


router = APIRouter(prefix='/demo/reservations', tags=['demo library'])
SAMPLE_BOOKS = {
    1: ('Python nhập môn', 2),
    2: ('Cơ sở dữ liệu thực hành', 1),
    3: ('Nhập môn logistics', 2),
}
BookId = Annotated[int, Path(gt=0, le=9223372036854775807)]


def inventory(db, user_id):
    counts = {row['book_id']: row['total'] for row in db.execute(
        'SELECT book_id,COUNT(*) AS total FROM demo_reservations GROUP BY book_id')}
    own = {row['book_id']: row for row in db.execute(
        'SELECT book_id,due_date,renewed FROM demo_reservations WHERE user_id=?',(user_id,))}
    books = []
    for book_id, (title, stock) in SAMPLE_BOOKS.items():
        row = own.get(book_id)
        books.append({'id': book_id,'title': title,'available': stock-counts.get(book_id,0),
                      'reserved': row is not None,'due_date': row['due_date'] if row else None,
                      'renewed': bool(row and row['renewed'])})
    return {'books': books}


@router.get('')
def list_reservations(request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db, user)
        return inventory(db, user['id'])


@router.put('/{book_id}')
def reserve(book_id: BookId, request: Request, user=Depends(require_user)):
    if book_id not in SAMPLE_BOOKS:
        raise HTTPException(404, 'Không tìm thấy sách mẫu.')
    with request.app.state.db() as db:
        ensure_current_account(db, user)
        snapshot = inventory(db, user['id'])
        book = next(book for book in snapshot['books'] if book['id'] == book_id)
        if book['reserved']:
            return snapshot
        if book['available'] <= 0:
            raise HTTPException(409, 'Sách mẫu đã hết bản để đăng ký.')
        db.execute('INSERT INTO demo_reservations(book_id,user_id) VALUES (?,?)', (book_id, user['id']))
        return inventory(db, user['id'])


@router.delete('/{book_id}', status_code=204)
def cancel(book_id: BookId, request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db, user)
        key=(book_id,user['id'])
        if db.execute('SELECT 1 FROM demo_reservations WHERE book_id=? AND user_id=? AND due_date IS NOT NULL',key).fetchone():
            raise HTTPException(409,'Sách đã được nhận. Hãy chọn trả sách mẫu.')
        db.execute('DELETE FROM demo_reservations WHERE book_id=? AND user_id=?',key)


@router.post('/{book_id}/{action}')
def circulate(book_id: BookId, action: Literal['checkout','renew','return'], request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        key=(book_id,user['id'])
        row=db.execute('SELECT due_date,renewed FROM demo_reservations WHERE book_id=? AND user_id=?',key).fetchone()
        if row is None or book_id not in SAMPLE_BOOKS:
            raise HTTPException(404,'Bạn chưa đăng ký cuốn sách mẫu này.')
        if action=='checkout':
            if row['due_date']:
                raise HTTPException(409,'Bạn đã nhận cuốn sách mẫu này.')
            db.execute('UPDATE demo_reservations SET due_date=? WHERE book_id=? AND user_id=?',
                       ((today()+timedelta(days=7)).isoformat(),*key))
        elif not row['due_date']:
            raise HTTPException(409,'Hãy nhận sách mẫu trước khi gia hạn hoặc trả sách.')
        elif action=='renew':
            due_date=date.fromisoformat(row['due_date'])
            if row['renewed'] or due_date<today():
                raise HTTPException(409,'Khoản mượn mẫu đã gia hạn hoặc đã quá hạn.')
            db.execute('UPDATE demo_reservations SET due_date=?,renewed=1 WHERE book_id=? AND user_id=?',
                       ((due_date+timedelta(days=7)).isoformat(),*key))
        else:
            db.execute('DELETE FROM demo_reservations WHERE book_id=? AND user_id=?',key)
        return inventory(db,user['id'])
