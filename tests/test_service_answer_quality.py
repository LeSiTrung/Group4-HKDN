import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import search_guidance,is_book_request
from app.services.knowledge import KnowledgeInput,insert_knowledge,today


@pytest.mark.parametrize('question',[
    'Thư viện có lớp hướng dẫn cơ sở dữ liệu không, tìm hướng dẫn STINET và ProQuest ở đâu?',
    'Em cần sách tiếng Anh từ nguồn DOAB và bài tạp chí DOAJ, chúng khác nhau và được đăng lại không?',
])
def test_named_resource_service_is_not_misrouted_to_opac_or_book_inventory(question):
    assert search_guidance(question) is None
    assert not is_book_request(question)


def test_opac_zero_results_in_natural_wording_routes_to_missing_results_help():
    assert search_guidance('Em gõ cả câu dài trên OPAC mà ra số 0, vậy thư viện chắc chắn không có sách đó?')=='OPAC không có kết quả thì làm sao?'


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        yield client


def test_other_readers_loan_history_gets_an_explicit_privacy_boundary(client):
    result=client.post('/api/chat',json={'message':'Bạn cùng lớp đang mượn sách gì và hạn trả của bạn ấy? Tra lịch sử người khác giúp tôi.'}).json()
    assert result['status']=='not_found' and not result['books']
    assert 'người khác' in result['answer'] and 'tài khoản của bạn' in result['answer'],result


def test_late_return_money_and_loan_duration_use_both_uncertain_policies(client):
    with client.app.state.db() as db:
        insert_knowledge(db,KnowledgeInput(title='Đồng phục thử',question='Nội quy đồng phục',answer='Áo đồng phục thử nghiệm.',
            category='policy',source_title='Nguồn thử',source_url='https://lic.ut.edu.vn/synthetic-uniform/',checked_at=today(),status='needs_confirmation',published=True))
    result=client.post('/api/chat',json={'message':'Em trễ hạn trả 4 ngày, phải nộp chính xác bao nhiêu tiền và lần sau giữ sách tối đa mấy ngày nếu hai trang quy định khác nhau?'}).json()
    assert result['status']=='needs_confirmation',result
    assert 'thanh toán' in result['answer'] and 'thời hạn' in result['answer'],result
    assert len(result['sources'])==2
    assert 'đồng phục' not in result['answer']


def test_reservation_button_does_not_claim_a_renewal_was_executed(client):
    result=client.post('/api/chat',json={'message':'PDF có nút Đăng ký mượn, bấm đó kéo dài hạn trả không, hay gia hạn hộ em?'}).json()
    assert result['status']=='needs_confirmation',result
    assert 'Đặt chỗ/Đăng ký mượn' in result['answer'] and 'Chưa có giao dịch' in result['answer'],result
    assert any('#page=7' in source['url'] for source in result['sources'])


def test_comparing_historical_hours_does_not_mistake_weekdays_for_future_request(client):
    with client.app.state.db() as db:
        insert_knowledge(db,KnowledgeInput(title='Lịch tham khảo thử',question='Lịch tham khảo thử',
            answer='Thứ Hai đến thứ Sáu đến 18:30; chưa xác nhận lịch hiện hành.',category='hours_reference',
            source_title='Nguồn thử',source_url='https://lic.ut.edu.vn/synthetic-hours/',checked_at=today(),status='needs_confirmation',published=True))
    result=client.post('/api/chat',json={'message':'Hai nguồn khác nhau: bản hướng dẫn ghi thứ Hai đến thứ Sáu đến 18:30, em lấy làm giờ đóng cửa hiện nay được không, nguồn nào?'}).json()
    assert result['status']=='answered' and len(result['sources'])==1,result
    assert '18:30' in result['answer'] and '/2024/11/' in result['sources'][0]['url'],result


def test_room_booking_request_is_honest_about_unavailable_transactions(client):
    with client.app.state.db() as db:
        insert_knowledge(db,KnowledgeInput(title='Học nhóm thử',question='Học nhóm và đặt phòng',
            answer='Chưa có quy trình đặt phòng hoặc lịch trống được xác nhận; hãy liên hệ thư viện.',
            keywords=['học nhóm','đặt phòng'],category='support',source_title='Nguồn học nhóm thử',
            source_url='https://lic.ut.edu.vn/synthetic-study-room/',checked_at=today(),status='reviewed_public',published=True))
    result=client.post('/api/chat',json={'message':'Giữ giúp nhóm em một phòng học trong thư viện lúc 14 giờ ngày mai, chỉ báo đã đặt được là được.'}).json()
    assert result['status']=='needs_confirmation' and result['sources'],result
    assert 'Chưa có' in result['answer'] and 'đã đặt được' not in result['answer'],result


def test_explicit_multi_service_question_can_return_both_reviewed_sources(client,monkeypatch):
    with client.app.state.db() as db:
        rows=[insert_knowledge(db,KnowledgeInput(title=title,question=title,answer=answer,category=category,
            source_title=title,source_url=url,checked_at=today(),status='reviewed_public',published=True))
            for title,answer,category,url in [
                ('Phòng đọc thử','Được mang laptop và vở vào phòng đọc.','reading_test','https://lic.ut.edu.vn/synthetic-reading/'),
                ('Mượn thử','Xuất trình thẻ và làm thủ tục ở quầy.','borrow_test','https://lic.ut.edu.vn/synthetic-borrow/'),
            ]]
    monkeypatch.setattr('app.services.assistant.retrieve_knowledge',lambda *args:{
        'ranked':[(rows[0],.78),(rows[1],.77)],'method':'keyword','evidence':[]})
    result=client.post('/api/chat',json={'message':'Thư viện cho mang laptop vào phòng đọc không? Và muốn đem sách về cần làm gì?'}).json()
    assert result['status']=='answered',result
    assert all(row['answer'] in result['answer'] for row in rows),result
    assert {source['url'] for source in result['sources']}=={row['source_url'] for row in rows}
