import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput,save_book
from app.services.knowledge import today


TITLE='Python thực hành qua dự án'
URL='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=987'


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            row=save_book(db,BookInput(title=TITLE,author='Tác giả thử nghiệm',year='2024',subjects='Python',
                source_url=URL,checked_at=today(),published=True))
            db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                (row['id'],URL,'2026-10-28','a'*64,'Python','Học Python qua các dự án thực hành.','Người học đã biết cú pháp Python.'))
        client.book_id=row['id']
        yield client


def ask(client,question):
    response=client.post('/api/chat',json={'message':question,'history':[
        {'role':'assistant','content':'Kết quả tìm tài liệu.','book_ids':[client.book_id]},
    ]})
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('question,facts',[
    (f'Tóm tắt ngắn gọn tài liệu “{TITLE}”.',['Học Python qua các dự án thực hành.']),
    (f'Sách “{TITLE}” của ai và in năm mấy?',['Tác giả thử nghiệm','2024']),
    (f'Sach “{TITLE}” cua ai va in nam nao?',['Tác giả thử nghiệm','2024']),
])
def test_colloquial_questions_about_a_quoted_title_stay_in_catalog(client,question,facts):
    response=client.post('/api/chat',json={'message':question})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['status']=='answered' and result['mode']=='catalog',result
    assert all(fact in result['answer'] for fact in facts),result
    assert [source['url'] for source in result['sources']]==[URL]


def test_author_and_year_are_one_readable_sentence_without_repeating_the_title(client):
    result=ask(client,'Cuốn đó do ai viết và xuất bản năm nào?')
    assert result['status']=='answered',result
    assert result['answer'].startswith(f'“{TITLE}”'),result
    assert result['answer'].count(TITLE)==1,result
    assert any('Tác giả thử nghiệm' in paragraph and '2024' in paragraph for paragraph in result['answer'].split('\n\n')),result
    assert result['sources']==[{'title':TITLE,'url':URL,'checked_at':today().isoformat()}]


def test_known_facts_and_missing_isbn_are_kept_without_repeated_attribution(client):
    result=ask(client,'Tác giả, năm xuất bản và ISBN của cuốn đó?')
    assert result['status']=='needs_confirmation',result
    assert all(value in result['answer'] for value in ['Tác giả thử nghiệm','2024','ISBN','chưa xác nhận']),result
    assert result['answer'].count(TITLE)==1,result
    assert result['answer'].count('Theo biểu ghi')<=1,result


def test_multiple_missing_fields_share_one_clear_uncertainty_message(client):
    result=ask(client,'ISBN, nhà xuất bản và vị trí kệ của cuốn đó?')
    assert result['status']=='needs_confirmation',result
    assert all(label in result['answer'] for label in ['ISBN','nhà xuất bản','vị trí kệ']),result
    assert result['answer'].count('chưa xác nhận')==1,result
    assert result['answer'].count('không tự suy đoán')<=1,result


def test_summary_and_audience_share_title_but_preserve_both_source_texts(client):
    result=ask(client,'Tóm tắt và đối tượng đọc của cuốn đó?')
    assert result['status']=='answered',result
    assert not result['answer'].startswith('Theo biểu ghi'),result
    assert result['answer'].count(TITLE)==1,result
    assert 'Học Python qua các dự án thực hành.' in result['answer'],result
    assert 'Người học đã biết cú pháp Python.' in result['answer'],result
    assert result['sources']==[{'title':TITLE,'url':URL,'checked_at':'2026-10-28'}]


def test_combined_short_and_long_facts_keep_their_distinct_review_dates(client):
    result=ask(client,'Tác giả, năm xuất bản, tóm tắt và đối tượng đọc của cuốn đó?')
    assert result['status']=='answered',result
    assert result['answer'].count(TITLE)==1,result
    assert all(fact in result['answer'] for fact in ['Tác giả thử nghiệm','2024','Học Python qua các dự án thực hành.','Người học đã biết cú pháp Python.']),result
    assert {source['checked_at'] for source in result['sources']}=={today().isoformat(),'2026-10-28'}


@pytest.mark.parametrize('missing,known_fact,missing_label',[
    ('author','2024','tác giả'),('year','Tác giả thử nghiệm','năm xuất bản'),
])
def test_one_missing_bibliographic_field_does_not_hide_the_known_fact(client,missing,known_fact,missing_label):
    with client.app.state.db() as db:
        db.execute('UPDATE books SET '+missing+"='' WHERE id=?",(client.book_id,))
    result=ask(client,'Tác giả và năm xuất bản của cuốn đó?')
    assert result['status']=='needs_confirmation',result
    assert known_fact in result['answer'] and missing_label in result['answer'],result
    assert result['answer'].count(TITLE)==1,result
    assert 'chưa xác nhận' in result['answer'],result
