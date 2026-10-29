from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        day=today().isoformat()
        with client.app.state.db() as db:
            db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('1',today().weekday(),'08:00','17:00',day,day,'Synthetic operator','https://lic.ut.edu.vn/','Synthetic schedule',day))
        yield client


@pytest.mark.parametrize('question',[
    'Giờ mở cửa hôm nay cơ sở 12',
    'Giờ mở cửa hôm nay cơ sở 1 và cơ sở 2',
    'Ngày mai cơ sở 1 mở cửa giống hôm nay không?',
])
def test_ambiguous_branch_or_different_date_cannot_use_today_schedule(client,question):
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status']=='clarify'
    assert '08:00' not in result['answer']


def test_return_deadline_is_not_mistaken_for_opening_hours(client):
    result=client.post('/api/chat',json={'message':'Mượn sách bao giờ phải trả?'}).json()
    assert result['status']=='needs_confirmation'
    assert 'quy-dinh-muon-tra-tai-lieu' in result['sources'][0]['url']


def test_unrelated_turn_does_not_resurrect_old_book_context(client):
    history=[{'role':'user','content':'Tìm sách Olympic cơ học'},{'role':'user','content':'Tôi muốn gia hạn sách'}]
    result=client.post('/api/chat',json={'message':'Tác giả là ai?','history':history}).json()
    assert not result['books']
    assert result['status']=='clarify'


def test_unresolved_book_reference_requests_a_title(client):
    result=client.post('/api/chat',json={'message':'Cuốn đó của tác giả nào?'}).json()
    assert result['status']=='clarify'
    assert not result['sources'] and not result['books']
