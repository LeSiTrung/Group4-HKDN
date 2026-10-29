import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .auth import require_user, public_user, ensure_current_account

router = APIRouter(tags=['history'])


def conversation(request, user, conversation_id):
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        row = db.execute('SELECT * FROM conversations WHERE id=? AND user_id=?', (conversation_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Không tìm thấy hội thoại.')
        messages = [dict(x) for x in db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id', (conversation_id,))]
    for message in messages:
        message['sources'] = json.loads(message['sources'])
        message['books'] = json.loads(message['books'])
    return {**dict(row), 'messages': messages}


@router.get('/conversations')
def conversations(request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        return [dict(x) for x in db.execute('SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC,id DESC', (user['id'],))]


@router.get('/conversations/{conversation_id}')
def get_conversation(conversation_id: int, request: Request, user=Depends(require_user)):
    return conversation(request, user, conversation_id)


@router.delete('/conversations/{conversation_id}')
def remove_conversation(conversation_id: int, request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        count = db.execute('DELETE FROM conversations WHERE id=? AND user_id=?', (conversation_id, user['id'])).rowcount
    if not count:
        raise HTTPException(404, 'Không tìm thấy hội thoại.')
    return {'ok': True}


@router.get('/export')
def export(request: Request, user=Depends(require_user)):
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        ids = [x['id'] for x in db.execute('SELECT id FROM conversations WHERE user_id=? ORDER BY id', (user['id'],))]
    return {'user': public_user(user), 'conversations': [conversation(request, user, i) for i in ids]}


class Feedback(BaseModel):
    message_id: int
    rating: int
    comment: str = Field(default='', max_length=1000)


@router.post('/feedback')
def feedback(body: Feedback, request: Request, user=Depends(require_user)):
    if body.rating not in (-1, 1):
        raise HTTPException(422, 'Đánh giá phải là -1 hoặc 1.')
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        row = db.execute("SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.user_id=? AND m.role='assistant'", (body.message_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Không tìm thấy câu trả lời.')
        db.execute('INSERT INTO feedback VALUES (?,?,?,?) ON CONFLICT(user_id,message_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment', (user['id'], body.message_id, body.rating, body.comment))
    return {'ok': True}
