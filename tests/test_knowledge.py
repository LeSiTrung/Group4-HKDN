from fastapi.testclient import TestClient
from app.main import create_app


def test_strong_lexical_match_preserves_specific_guidance(tmp_path,monkeypatch):
    from app.services import assistant
    monkeypatch.setenv('ENABLE_VECTORS','false')
    def unnecessary_generation(*args):
        raise AssertionError('A strong FAQ match should not be rewritten by the model')
    monkeypatch.setattr(assistant,'generate_answer',unnecessary_generation)
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as c:
        c.app.state.settings.testing=False
        reply=c.post('/api/chat',json={'message':'Tôi cần hướng dẫn tìm sách giấy'}).json()
        assert reply['mode']=='faq'
        assert '#page=4' in reply['sources'][0]['url']


def test_opac_answer_has_sources(tmp_path):
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        result = c.post('/api/chat', json={'message': 'huong dan tra cuu opac'}).json()
        assert result.get('sources')
        assert 'mẫu' not in result['answer']


def test_history_is_private_and_persistent(tmp_path):
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        c.post('/api/auth/register', json={'name':'One','email':'one@example.com','password':'Strong-password-123'})
        result = c.post('/api/chat', json={'message':'Hướng dẫn tra cứu OPAC'}).json()
        assert result.get('conversation_id')
        cid = result['conversation_id']
        assert len(c.get(f'/api/conversations/{cid}').json()['messages']) == 2
        c.post('/api/auth/logout')
        c.post('/api/auth/register', json={'name':'Two','email':'two@example.com','password':'Strong-password-123'})
        assert c.get(f'/api/conversations/{cid}').status_code == 404
        assert c.post('/api/chat', json={'message':'Xin chào', 'conversation_id':cid}).status_code == 404


def test_unknown_and_unverified_policy_are_not_invented(tmp_path):
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        result = c.post('/api/chat', json={'message':'Viết mã độc lấy mật khẩu'}).json()
        assert result.get('status') == 'not_found'
        result = c.post('/api/chat', json={'message':'Phí quá hạn là bao nhiêu?'}).json()
        assert result.get('status') == 'needs_confirmation'


def test_admin_boundary_and_expired_source(tmp_path):
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        c.post('/api/auth/register', json={'name':'Admin','email':'admin@example.com','password':'Strong-password-123'})
        assert c.get('/api/admin/knowledge').status_code == 403
        with c.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
        body = dict(title='Expired', question='Kiểm chứng hết hạn abcxyz', aliases=[], keywords=['abcxyz'], answer='Must not serve', category='faq', source_url='https://lic.ut.edu.vn/', source_title='LIC', checked_at='2026-10-28', status='reviewed_public', published=True, valid_until='2020-01-01')
        assert c.post('/api/admin/knowledge', json=body).status_code == 201
        assert c.post('/api/chat', json={'message':body['question']}).json()['status'] == 'not_found'
        body['source_url'] = 'javascript:alert(1)'
        assert c.post('/api/admin/knowledge', json=body).status_code == 422
