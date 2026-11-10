import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput,save_book
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            for index,(title,author) in enumerate([
                ('Python GUI Programming cookbook : tkinter and PyQt5','Burkhard A. Meier'),
                ('Giáo trình lập trình Python','Trần Đăng Hưng (chủ biên)'),
                ('Tài nguyên thực vật Việt Nam : Giáo trình','Người khác'),
            ],1):
                save_book(db,BookInput(title=title,author=author,subjects='Tiếng Việt' if index==2 else '',year='2024',source_url=f'https://lic.ut.edu.vn/synthetic-framing-{index}/',checked_at=today(),published=True))
        yield client


@pytest.mark.parametrize('question,title',[
    ('Em tìm sách Python làm giao diện bằng tkinter với PyQt5, hình như tên có chữ cookbook. Giúp em xác định đúng cuốn, tác giả và năm theo bản ghi thư viện, kèm nơi xem chi tiết.','Python GUI Programming cookbook : tkinter and PyQt5'),
    ('Tìm cho em cuốn giáo trình Python tiếng Việt có Trần Đăng Hưng chủ biên. Bản ghi thư viện ghi tên tài liệu, những người tham gia và năm nào?','Giáo trình lập trình Python'),
])
def test_search_intent_omits_question_framing_but_keeps_subject_and_author(client,question,title):
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status']=='answered',result
    assert result['books'][0]['title']==title,result
    assert not any('thực vật' in book['title'] for book in result['books']),result
