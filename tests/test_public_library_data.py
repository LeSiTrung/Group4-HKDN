import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.main import create_app
from app.services.knowledge import KnowledgeInput, insert_knowledge, today


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            insert_knowledge(db, KnowledgeInput(title='Reference hours', question='Giờ phục vụ thường lệ',
                answer='Lịch thường lệ tham khảo: 07:30–20:30. Chưa xác nhận lịch hôm nay; kiểm tra ngày lễ.',
                category='hours_reference', source_url='https://lic.ut.edu.vn/guide.pdf#page=12',
                source_title='Synthetic official guide', checked_at=today(), status='needs_confirmation', published=True))
        yield client


@pytest.mark.parametrize('message', ['Giờ mở cửa mặc định của thư viện?', 'Thu vien mo cua may gio?', 'Thời gian phục vụ thường lệ cơ sở 1'])
def test_regular_hours_are_a_sourced_reference_not_current_verification(client, message):
    result=client.post('/api/chat', json={'message': message}).json()
    assert result['status']=='needs_confirmation' and result['mode']=='faq'
    assert '07:30' in result['answer'] and 'thường lệ' in result['answer']
    assert result['sources'][0]['url'].endswith('#page=12')


def test_today_without_verified_schedule_can_show_clearly_labelled_reference(client):
    result=client.post('/api/chat', json={'message': 'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert result['status']=='needs_confirmation'
    assert '07:30' in result['answer'] and 'chưa' in result['answer'].lower()
    assert result['sources'][0]['url'].endswith('#page=12')


@pytest.mark.parametrize('message', ['Giờ mở cửa thường lệ của thư viện?', 'Giờ mở cửa hôm nay cơ sở 1'])
def test_conflicting_hours_retain_both_references_without_selecting_a_current_rule(client, message):
    with client.app.state.db() as db:
        insert_knowledge(db, KnowledgeInput(title='Another public guide', question='Lịch tham khảo trong hướng dẫn mới',
            answer='Tài liệu khác ghi 07:30–18:30. Chưa xác nhận lịch hiện hành.',
            category='hours_reference', source_url='https://lic.ut.edu.vn/another-guide.pdf#page=12',
            source_title='Another synthetic official guide', checked_at=today(), status='needs_confirmation', published=True))
    response=client.post('/api/chat', json={'message':message}).json()
    assert response['status']=='needs_confirmation' and response['mode']=='faq'
    assert 'khác nhau' in response['answer']
    assert '07:30–20:30' in response['answer'] and '07:30–18:30' in response['answer']
    assert {row['url'] for row in response['sources']}=={'https://lic.ut.edu.vn/guide.pdf#page=12',
        'https://lic.ut.edu.vn/another-guide.pdf#page=12'}
    day=today()
    with client.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('1',day.weekday(),'09:00','15:00',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day)))
    confirmed=client.post('/api/chat',json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert confirmed['status']=='answered' and '09:00' in confirmed['answer']
    assert len(confirmed['sources'])==1 and confirmed['sources'][0]['url']=='https://lic.ut.edu.vn/current'


@pytest.mark.parametrize('message', ['Giờ mở cửa hôm nay cơ sở 12', 'Giờ mở cửa hôm nay cơ sở 1 và cơ sở 2',
    'Giờ mở cửa ngày mai cơ sở 1', 'Giờ mở cửa ngày lễ cơ sở 1', 'Giờ mở cửa hôm nay cơ sở 1 và ngày mai'])
def test_reference_does_not_answer_invalid_branch_future_date_or_holiday(client, message):
    result=client.post('/api/chat', json={'message': message}).json()
    assert result['status']=='clarify' and '07:30' not in result['answer']


def test_verified_today_schedule_precedes_reference_and_withdrawal_is_respected(client):
    day=today()
    with client.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('1',day.weekday(),'09:00','15:00',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day)))
    result=client.post('/api/chat', json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert result['status']=='answered' and '09:00' in result['answer'] and '07:30' not in result['answer']
    with client.app.state.db() as db:
        db.execute("UPDATE knowledge SET published=0 WHERE category='hours_reference'")
    result=client.post('/api/chat', json={'message':'Giờ mở cửa mặc định của thư viện?'}).json()
    assert '07:30' not in result['answer'] and not result['sources']


def test_import_is_idempotent_and_preserves_operator_changes(tmp_path, monkeypatch, capsys):
    from app.database.connection import Store
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'runtime'))
    entry={'title':'Reviewed service','question':'Dịch vụ thử nghiệm','answer':'Published source summary',
        'category':'service','source_url':'https://lic.ut.edu.vn/service','source_title':'Service',
        'checked_at':str(today()),'status':'reviewed_public','published':True}
    pack=tmp_path/'pack.json'
    pack.write_text(json.dumps([entry]),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['app.cli','import-knowledge',str(pack)])
    cli.main()
    assert json.loads(capsys.readouterr().out)['imported']==1
    store=Store(tmp_path/'runtime/library.sqlite3')
    with store.connect() as db:
        db.execute("UPDATE knowledge SET answer='Operator edit',published=0 WHERE source_url=?",(entry['source_url'],))
    cli.main()
    assert json.loads(capsys.readouterr().out)=={'imported':0,'skipped':1}
    with store.connect() as db:
        rows=db.execute('SELECT answer,published FROM knowledge WHERE source_url=?',(entry['source_url'],)).fetchall()
    assert len(rows)==1 and rows[0]['answer']=='Operator edit' and rows[0]['published']==0


def test_invalid_import_pack_does_not_write_partial_content(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'runtime'))
    pack=tmp_path/'invalid.json'
    valid={'title':'Valid first row','question':'Question','answer':'Answer','category':'service',
        'source_url':'https://lic.ut.edu.vn/valid','source_title':'Source','checked_at':str(today()),'status':'reviewed_public'}
    pack.write_text(json.dumps([valid,{'title':'Incomplete source'}]),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['app.cli','import-knowledge',str(pack)])
    with pytest.raises(SystemExit):
        cli.main()
    assert not (tmp_path/'runtime/library.sqlite3').exists()


def test_dated_public_pack_validates_and_preserves_hours_uncertainty():
    root=Path(__file__).resolve().parents[1]
    rows=[KnowledgeInput.model_validate(row) for row in json.loads((root/'data/faq/public-library-2026-10-31.json').read_text(encoding='utf-8'))]
    assert len({(row.question,row.source_url) for row in rows})==len(rows)==10
    hours=next(row for row in rows if row.category=='hours_reference')
    assert hours.status=='needs_confirmation' and not hours.verified_by and not hours.valid_from
    assert '07:30–12:00 và 13:00–16:30' in hours.answer
    assert 'Chủ nhật' in hours.answer and 'không tự hiểu là đóng cửa' in hours.answer
    assert hours.source_url.endswith('#page=12')
    assert not any(row.status=='verified' for row in rows)


@pytest.mark.parametrize('question,source,status,fact', [
    ('Giờ mở cửa thường lệ của thư viện?', '2024/11/', 'needs_confirmation', '08:30–16:30'),
    ('Sinh viên đến thư viện có cần mặc đồng phục không?', 'mac-dong-phuc', 'needs_confirmation', '10/06/2024'),
    ('Thư viện hỗ trợ xuất bản giáo trình và kỷ yếu hội thảo không?', 'xuat-ban-phat-hanh', 'answered', 'đã nghiệm thu'),
    ('Thư viện có lớp hướng dẫn khai thác cơ sở dữ liệu cho sinh viên mới không?', 'photo-scan', 'answered', 'sinh viên đầu khóa'),
])
def test_new_reviewed_pack_answers_with_source_and_uncertainty(client,question,source,status,fact):
    pack=Path(__file__).resolve().parents[1]/'data/faq/public-library-2026-11-01.json'
    rows=[KnowledgeInput.model_validate(row) for row in json.loads(pack.read_text(encoding='utf-8'))]
    assert len(rows)==4 and not any(row.status=='verified' or row.verified_by or row.valid_from for row in rows)
    with client.app.state.db() as db:
        for row in rows:
            insert_knowledge(db,row)
    response=client.post('/api/chat',json={'message':question}).json()
    assert response['status']==status and fact in response['answer']
    assert any(source in row['url'] for row in response['sources'])
