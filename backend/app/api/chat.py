import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from .auth import optional_user,ensure_current_account
from typing import Literal

router = APIRouter(tags=["chat"])


class HistoryTurn(BaseModel):
    role:Literal['user','assistant']
    content:str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, strict=True)
    conversation_id: int | None = Field(default=None,gt=0)
    history:list[HistoryTurn]=Field(default_factory=list,max_length=6)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Vui lòng nhập câu hỏi.')
        return value


class ChatResponse(BaseModel):
    answer: str
    status: str
    sources: list[dict]
    suggestions: list[str]
    mode: str
    conversation_id: int | None = None
    message_id: int | None = None
    books:list[dict]=Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest,request:Request,user=Depends(optional_user)):
    cid = payload.conversation_id
    history=[] if user else [turn.model_dump() for turn in payload.history]
    if cid:
        with request.app.state.db() as db:
            if not user or not db.execute('SELECT id FROM conversations WHERE id=? AND user_id=?',(cid,user['id'])).fetchone():
                raise HTTPException(404,'Không tìm thấy hội thoại.')
            ensure_current_account(db,user)
            history = [dict(x) for x in db.execute('SELECT role,content,context_query FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 6',(cid,))][::-1]
    result = request.app.state.answer(payload.message,history)
    mid = None
    if user:
        with request.app.state.db() as db:
            ensure_current_account(db,user)
            if cid:
                if not db.execute('SELECT id FROM conversations WHERE id=? AND user_id=?',(cid,user['id'])).fetchone():
                    raise HTTPException(409,'Hội thoại đã được xóa. Hãy bắt đầu cuộc trò chuyện mới.')
            else:
                cid = db.execute('INSERT INTO conversations(user_id,title) VALUES (?,?)',(user['id'],payload.message.strip()[:80])).lastrowid
            db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user',?)",(cid,payload.message))
            mid = db.execute("INSERT INTO messages(conversation_id,role,content,sources,status,mode,books,context_query) VALUES (?,'assistant',?,?,?,?,?,?)",
                (cid,result['answer'],json.dumps(result['sources'],ensure_ascii=False),result['status'],result['mode'],json.dumps(result.get('books',[]),ensure_ascii=False),result.get('context_query',''))).lastrowid
            db.execute("UPDATE conversations SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",(cid,))
    return {**result,'conversation_id':cid,'message_id':mid}
