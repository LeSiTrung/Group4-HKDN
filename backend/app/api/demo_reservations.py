from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from .auth import ensure_current_account, require_user


router = APIRouter(prefix='/demo/reservations', tags=['demo library'])
SAMPLE_BOOKS = {
    1: ('Python nhập môn', 2),
    2: ('Cơ sở dữ liệu thực hành', 1),
    3: ('Nhập môn logistics', 2),
}
BookId = Annotated[int, Path(gt=0, le=9223372036854775807)]


def inventory(db, user_id):
    counts = {row['book_id']: (row['total'], bool(row['mine'])) for row in db.execute(
        'SELECT book_id, COUNT(*) AS total, MAX(user_id=?) AS mine FROM demo_reservations GROUP BY book_id',
        (user_id,),
    )}
    books = []
    for book_id, (title, stock) in SAMPLE_BOOKS.items():
        total, reserved = counts.get(book_id, (0, False))
        books.append({'id': book_id, 'title': title, 'available': stock - total, 'reserved': reserved})
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
        db.execute('DELETE FROM demo_reservations WHERE book_id=? AND user_id=?', (book_id, user['id']))
