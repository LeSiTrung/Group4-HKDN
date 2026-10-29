import json
from typing import Literal
from fastapi import APIRouter, Depends, Query, Request
from .auth import require_admin

router = APIRouter(prefix='/admin', tags=['administration'], dependencies=[Depends(require_admin)])


@router.get('/feedback')
def review_feedback(request: Request, rating: Literal['-1', '1'] | None = None,
                    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=50)):
    joined = "FROM feedback f JOIN messages m ON m.id=f.message_id JOIN conversations c ON c.id=m.conversation_id WHERE m.role='assistant' AND c.user_id=f.user_id"
    filtered = joined + (' AND f.rating=?' if rating else '')
    params = (int(rating),) if rating else ()
    with request.app.state.db() as db:
        summary = dict(db.execute('SELECT count(CASE WHEN f.rating=1 THEN 1 END) AS positive, count(CASE WHEN f.rating=-1 THEN 1 END) AS negative ' + joined).fetchone())
        total = db.execute('SELECT count(*) ' + filtered, params).fetchone()[0]
        rows = [] if (page-1)*page_size >= total else db.execute("""SELECT m.id AS message_id,
            coalesce((SELECT CASE WHEN previous.role='user' THEN previous.content ELSE '' END
                FROM messages previous WHERE previous.conversation_id=m.conversation_id AND previous.id<m.id
                ORDER BY previous.id DESC LIMIT 1),'') AS question,
            m.content AS answer, f.rating, f.comment, m.status, m.mode, m.sources """ + filtered +
            ' ORDER BY m.id DESC LIMIT ? OFFSET ?', (*params, page_size, (page-1)*page_size)).fetchall()
    items = [{**dict(row), 'sources': json.loads(row['sources'])} for row in rows]
    return {'items': items, 'total': total, 'page': page, 'page_size': page_size, 'summary': summary}
