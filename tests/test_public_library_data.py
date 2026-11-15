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


@pytest.mark.parametrize('message', ['Giờ mở cửa thường lệ của thư viện?', 'Giờ mở cửa hôm nay cơ sở 1'])
def test_old_guides_do_not_override_current_hours(client, message):
    with client.app.state.db() as db:
        insert_knowledge(db, KnowledgeInput(title='Another public guide', question='Lịch tham khảo trong hướng dẫn mới',
            answer='Tài liệu khác ghi 07:30–18:30. Chưa xác nhận lịch hiện hành.',
            category='hours_reference', source_url='https://lic.ut.edu.vn/another-guide.pdf#page=12',
            source_title='Another synthetic official guide', checked_at=today(), status='needs_confirmation', published=True))
    response=client.post('/api/chat', json={'message':message}).json()
    assert response['status']=='answered' and response['mode']=='faq'
    assert '20:30' not in response['answer']
    assert len(response['sources'])==1 and '/2024/11/' in response['sources'][0]['url']
    day=today()
    with client.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('1',day.weekday(),'09:00','15:00',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day)))
    confirmed=client.post('/api/chat',json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert confirmed['status']=='answered' and '09:00' in confirmed['answer']
    assert len(confirmed['sources'])==1 and confirmed['sources'][0]['url']=='https://lic.ut.edu.vn/current'


@pytest.mark.parametrize('message', ['Giờ mở cửa hôm nay cơ sở 12',
    'Giờ mở cửa hôm nay cơ sở 1 và ngày mai'])
def test_hours_ask_for_one_valid_branch_and_day(client, message):
    result=client.post('/api/chat', json={'message': message}).json()
    assert result['status']=='clarify' and '07:30' not in result['answer']


def test_verified_today_schedule_precedes_default_and_old_guides_can_be_withdrawn(client):
    day=today()
    with client.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('1',day.weekday(),'09:00','15:00',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day)))
    result=client.post('/api/chat', json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert result['status']=='answered' and '09:00' in result['answer'] and '07:30' not in result['answer']
    with client.app.state.db() as db:
        db.execute("UPDATE knowledge SET published=0 WHERE category='hours_reference'")
    result=client.post('/api/chat', json={'message':'Giờ mở cửa mặc định của thư viện?'}).json()
    assert result['status']=='answered' and '07:30–18:30' in result['answer']


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
    ('Giờ mở cửa thường lệ của thư viện?', '2024/11/', 'answered', '08:30–16:30'),
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


@pytest.fixture
def lic_update(client):
    pack=Path(__file__).resolve().parents[1]/'data/faq/public-library-2026-11-12.json'
    with client.app.state.db() as db:
        for row in json.loads(pack.read_text(encoding='utf-8')):
            insert_knowledge(db,KnowledgeInput.model_validate(row))
    return client


def test_lic_contact_remains_available_without_reference_guides(lic_update):
    with lic_update.app.state.db() as db:
        db.execute("UPDATE knowledge SET published=0 WHERE category='hours_reference'")
    question='Liên hệ ở đâu để xác nhận giờ mở cửa của thư viện UTH?'
    result=lic_update.post('/api/chat',json={'message':question}).json()
    assert result['status']=='answered' and '35.126.169' in result['answer'],result
    assert [row['url'] for row in result['sources']]==['https://lic.ut.edu.vn/lien-he/']


def test_published_campus_directory_keeps_the_homepage_source(lic_update):
    result=lic_update.post('/api/chat',json={'message':'Thư viện cơ sở 2 ở đâu?'}).json()
    assert result['status']=='answered' and 'P003' in result['answer'] and 'An Khánh' in result['answer'],result
    assert [row['url'] for row in result['sources']]==['https://lic.ut.edu.vn/']


@pytest.mark.parametrize('question',[
    'Thư viện giới thiệu những cơ sở dữ liệu điện tử nào cho người đọc?',
    'Thu vien gioi thieu nhung co so du lieu dien tu nao cho ban doc?',
])
def test_public_database_overview_uses_reviewed_resource_faq(lic_update,question):
    pack=Path(__file__).resolve().parents[1]/'data/faq/public-library-2026-11-01.json'
    with lic_update.app.state.db() as db:
        for row in json.loads(pack.read_text(encoding='utf-8')):
            insert_knowledge(db,KnowledgeInput.model_validate(row))
    result=lic_update.post('/api/chat',json={'message':question}).json()
    assert result['status']=='answered' and 'ProQuest' in result['answer'] and 'STINET' in result['answer'],result
    assert any('thong-tin-cac-tai-lieu-co-ban-quyen' in s['url'] for s in result['sources'])
    assert not result['books']


@pytest.mark.parametrize('location,campuses', [('cơ sở 1 và 2', {'1', '2'}), ('An Khánh', {'2'}), ('cơ sở 1, 2 và 3', {'1', '2', '3'})])
def test_combined_hours_and_addresses_use_the_same_campuses(lic_update, location, campuses):
    result = lic_update.post('/api/chat', json={'message': f'Thư viện ở đâu và mở cửa lúc mấy giờ tại {location}?'}).json()
    assert result['status'] == 'answered', result
    address, _ = result['answer'].split('\n\n', 1)
    assert {line.split()[3].rstrip(':') for line in address.splitlines()[1:]} == campuses


@pytest.mark.parametrize('location', ['cơ sở 1 và 4', 'cơ sở 1, 4 và 3'])
def test_hours_ask_about_invalid_campus_in_a_list(lic_update, location):
    result = lic_update.post('/api/chat', json={'message': f'Thư viện mở cửa ngày mai ở {location}?'}).json()
    assert result['status'] == 'clarify', result


def test_named_campus_selects_the_approved_schedule_and_conflicting_campus_asks(lic_update):
    day=today()
    with lic_update.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('2',day.weekday(),'09:00','15:00',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day)))
    result=lic_update.post('/api/chat',json={'message':'Giờ mở cửa hôm nay ở An Khánh?'}).json()
    assert result['status']=='answered' and '09:00–15:00' in result['answer'],result
    assert [row['url'] for row in result['sources']]==['https://lic.ut.edu.vn/current']
    conflict=lic_update.post('/api/chat',json={'message':'Giờ mở cửa hôm nay cơ sở 1 ở An Khánh?'}).json()
    assert conflict['status']=='clarify' and '09:00' not in conflict['answer'],conflict


def test_interlibrary_policy_numbers_apply_to_explicit_interlibrary_queries_only(lic_update):
    result=lic_update.post('/api/chat',json={'message':'Mượn liên thư viện có phí không và được gia hạn bao lâu?'}).json()
    assert result['status']=='needs_confirmation',result
    assert all(fact in result['answer'] for fact in ('01/07/2025','30 ngày','7 ngày','phí vận chuyển')),result
    assert [row['url'].endswith('Chinhsachmuonlienthuvien.pdf') for row in result['sources']]==[True]
    domestic=lic_update.post('/api/chat',json={'message':'Thư viện cho mượn bao lâu và có phí không?'}).json()
    assert '30 ngày' not in domestic['answer'],domestic
    assert not any(row['url'].endswith('Chinhsachmuonlienthuvien.pdf') for row in domestic['sources']),domestic


@pytest.mark.parametrize('question,facts',[
    ('Giờ mở cửa mặc định của thư viện?', ('07:30–18:30','08:30–16:30','Chủ nhật','ba cơ sở')),
    ('Thu vien thu 7 co mo khong?', ('Thứ Bảy','08:30–16:30')),
    ('Sáng thứ Hai thư viện mở lúc mấy giờ?', ('Thứ Hai','07:30')),
    ('Mấy giờ đóng cửa thứ 6 ở An Khánh?', ('Thứ Sáu','18:30','cơ sở 2')),
    ('Chủ nhật thư viện có mở cửa không?', ('Chủ nhật','nghỉ')),
    ('Giờ mở cửa ngày lễ cơ sở 1?', ('Lễ','Tết','nghỉ')),
])
def test_common_hours_use_the_current_lic_guide(client,question,facts):
    reply=client.post('/api/chat',json={'message':question}).json()
    assert reply['status']=='answered' and not reply['books'],reply
    assert all(fact.lower() in reply['answer'].lower() for fact in facts),reply
    assert '20:30' not in reply['answer'],reply
    assert len(reply['sources'])==1 and '/2024/11/' in reply['sources'][0]['url']


def test_compares_documented_hours_when_reader_asks_about_both_sources(lic_update):
    pack=Path('data/faq/public-library-2026-10-31.json')
    with lic_update.app.state.db() as db:
        for row in json.loads(pack.read_text(encoding='utf-8')):
            if row['category']=='hours_reference':
                insert_knowledge(db,KnowledgeInput.model_validate(row))
    reply=lic_update.post('/api/chat',json={'message':
        'Tài liệu cũ nói cơ sở 1 đóng cửa 20:30, còn bản hướng dẫn khác ghi 18:30. Hai mốc này thuộc nguồn nào?'}).json()
    assert reply['status']=='answered' and '20:30' in reply['answer'] and '18:30' in reply['answer'],reply
    assert 'lịch chung' in reply['answer'] and 'lịch riêng' in reply['answer'],reply
    assert {url['url'].split('/uploads/')[1][:7] for url in reply['sources']}=={'2022/10','2024/11'}


@pytest.mark.parametrize('question,clock,expected',[
    ('Thư viện có mở cửa ở cơ sở 2 lúc 19h không?', '19:00', 'ngoài giờ phục vụ'),
    ('Thư viện cơ sở 2 có mở cửa thứ Bảy lúc 17h không?', '17:00', 'ngoài giờ phục vụ'),
    ('Thư viện cơ sở 2 có mở cửa thứ Hai lúc 15:30 không?', '15:30', 'trong khung giờ phục vụ'),
    ('Thư viện cơ sở 2 có mở cửa thứ Hai lúc 3 giờ chiều không?', '15:00', 'trong khung giờ phục vụ'),
])
def test_hours_answers_a_specific_clock_time(client,question,clock,expected):
    reply=client.post('/api/chat',json={'message':question}).json()
    assert reply['status']=='answered' and all(x in reply['answer'] for x in (clock,expected,'lịch chung','cơ sở 2')),reply
    assert reply['sources'] and not reply['books']


@pytest.mark.parametrize('question,windows',[
    ('Giờ phục vụ của thư viện?', ('07:30–18:30','08:30–16:30','Lễ, Tết')),
    ('Giờ phục vụ cơ sở 1, 2 và 3?', ('07:30–18:30','08:30–16:30')),
    ('Giờ phục vụ cơ sở 1, cơ sở 2 và cơ sở 3 thứ Bảy?', ('08:30–16:30',)),
    ('Giờ mở cửa ngày lễ?', ('nghỉ phục vụ',)),
])
def test_hours_lists_each_campus_with_its_hours(client,question,windows):
    reply=client.post('/api/chat',json={'message':question}).json()
    assert reply['status']=='answered' and not reply['books'],reply
    lines=[line for line in reply['answer'].splitlines() if line.startswith('Cơ sở ')]
    assert [line.split()[2] for line in lines]==['1','2','3'],reply
    assert all(all(window in line for window in windows) for line in lines),reply


def test_today_and_tomorrow_use_the_right_weekday_without_a_campus(client,monkeypatch):
    from datetime import date
    monkeypatch.setattr('app.services.assistant.today',lambda:date(2026,11,14))
    saturday=client.post('/api/chat',json={'message':'Thư viện mở cửa lúc mấy giờ hôm nay?'}).json()
    sunday=client.post('/api/chat',json={'message':'Thư viện mở cửa ngày mai không?'}).json()
    assert saturday['status']=='answered' and '08:30–16:30' in saturday['answer'],saturday
    assert sunday['status']=='answered' and 'Chủ nhật' in sunday['answer'] and 'nghỉ' in sunday['answer'].lower(),sunday
    for reply, window in [(saturday,'08:30–16:30'),(sunday,'nghỉ phục vụ')]:
        assert all(f'Cơ sở {campus} — {window}' in reply['answer'] for campus in (1,2,3)),reply


def test_weekday_followup_uses_the_hours_topic_and_campus(client):
    history=[{'role':'user','content':'Giờ mở cửa hôm nay ở An Khánh?'}]
    result=client.post('/api/chat',json={'message':'Còn thứ 7 thì sao?','history':history}).json()
    assert result['status']=='answered' and '08:30–16:30' in result['answer'] and 'cơ sở 2' in result['answer'],result
    assert all(f'cơ sở {campus}' not in result['answer'].lower() for campus in (1,3)),result


def test_hours_followup_does_not_treat_displayed_clock_times_as_campuses(client):
    history = [{'role': 'assistant', 'content': 'Lịch phục vụ Thứ Sáu tại cơ sở 1 và 2.\n'
                                               'Cơ sở 1 — 07:30–18:30\nCơ sở 2 — 07:30–18:30'}]
    result = client.post('/api/chat', json={'message': 'Còn thứ 7 thì sao?', 'history': history}).json()
    assert result['status'] == 'answered', result
    assert 'tại cơ sở 1 và 2' in result['answer']


def test_today_without_a_campus_mentions_a_dated_closure(client):
    day=today()
    with client.app.state.db() as db:
        db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at,closed) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            ('2',day.weekday(),'','',str(day),str(day),'Synthetic operator','https://lic.ut.edu.vn/current','Current',str(day),1))
    result=client.post('/api/chat',json={'message':'Giờ mở cửa hôm nay của thư viện?'}).json()
    assert result['status']=='answered' and 'Cơ sở 2 — nghỉ phục vụ' in result['answer'],result
    for campus in (1,3):
        assert any(line.startswith(f'Cơ sở {campus} — ') and 'lịch chung' in line for line in result['answer'].splitlines()),result
    assert any(row['url']=='https://lic.ut.edu.vn/current' for row in result['sources']),result
    at_clock=client.post('/api/chat',json={'message':'Thư viện cơ sở 2 có mở cửa hôm nay lúc 10h không?'}).json()
    assert '10:00' in at_clock['answer'] and 'Cơ sở 2 — ngoài giờ phục vụ (nghỉ phục vụ)' in at_clock['answer'],at_clock
    assert [row['url'] for row in at_clock['sources']]==['https://lic.ut.edu.vn/current']
