from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


HEADERS = {'X-Requested-With': 'LibraryAssistant'}
QUESTION = 'vậy bạn có thể đăng kí mượn sách giúp tôi được không'
PATH = '/api/demo/reservations'


def register(client, email):
    response = client.post('/api/auth/register', json={
        'email': email, 'name': 'Bạn đọc thử', 'password': 'synthetic-demo-password',
    })
    assert response.status_code == 201


def test_sample_stock_and_reservations_are_private_and_atomic(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS', 'true')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as first:
        assert first.get(PATH).status_code == 401
        with TestClient(first.app, headers=HEADERS) as second:
            register(first, 'one@example.test')
            register(second, 'two@example.test')
            books = first.get(PATH).json()['books']
            book_id = next(book['id'] for book in books if book['available'] == 1)
            route = f'{PATH}/{book_id}'
            assert first.put(f'{PATH}/999999').status_code == 404
            with ThreadPoolExecutor(2) as executor:
                statuses = list(executor.map(lambda client: client.put(route).status_code, (first, second)))
            assert sorted(statuses) == [200, 409]
            winner, other = (first, second) if statuses[0] == 200 else (second, first)
            assert winner.put(route).status_code == 200
            assert other.delete(route).status_code == 204
            assert other.put(route).status_code == 409
            assert not any(book['reserved'] for book in other.get(PATH).json()['books'])
            assert winner.delete(route).status_code == 204
            assert other.put(route).status_code == 200


def test_sample_circulation_keeps_stock_and_due_date_consistent(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS', 'true')
    monkeypatch.setattr('app.api.demo_reservations.today',lambda: date(2026,11,14),raising=False)
    route=f'{PATH}/2'
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as first, \
         TestClient(first.app, headers=HEADERS) as other:
        register(first,'one@example.test')
        register(other,'two@example.test')
        assert first.put(route).status_code==200
        assert other.post(route+'/checkout').status_code==404
        response=first.post(route+'/checkout')
        assert response.status_code==200,response.text
        book=response.json()['books'][1]
        assert book['available']==0 and book['due_date']=='2026-11-21' and not book['renewed']
        assert first.post(route+'/checkout').status_code==409
        assert first.delete(route).status_code==409
        assert other.put(route).status_code==409
        assert other.get(PATH).json()['books'][1]['due_date'] is None
        with ThreadPoolExecutor(2) as executor:
            attempts=list(executor.map(lambda _: first.post(route+'/renew'),range(2)))
        assert sorted(r.status_code for r in attempts)==[200,409]
        renewed=first.get(PATH).json()['books'][1]
        assert renewed['due_date']=='2026-11-28' and renewed['renewed']
        assert other.post(route+'/return').status_code==404
        returned=first.post(route+'/return').json()['books'][1]
        assert returned['available']==1 and returned['due_date'] is None and not returned['reserved']
        assert other.put(route).status_code==200


def test_existing_reservation_can_be_checked_out_after_upgrade(tmp_path, monkeypatch):
    import sqlite3
    path=tmp_path/'library.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE demo_reservations (book_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(book_id,user_id))')
    monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS','true')
    with TestClient(create_app(tmp_path,testing=True),headers=HEADERS) as client:
        register(client,'reader@example.test')
        with client.app.state.db() as db:
            db.execute('INSERT INTO demo_reservations(book_id,user_id) SELECT 2,id FROM users')
        assert client.get(PATH).json()['books'][1]['due_date'] is None
        assert client.post(PATH+'/2/checkout').status_code==200


def test_overdue_sample_loan_can_be_returned_but_not_renewed(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS','true')
    route=PATH+'/2'
    with TestClient(create_app(tmp_path,testing=True),headers=HEADERS) as client:
        register(client,'reader@example.test')
        assert client.put(route).status_code==200
        assert client.post(route+'/checkout').status_code==200
        with client.app.state.db() as db:
            db.execute("UPDATE demo_reservations SET due_date='2000-01-01'")
        assert client.post(route+'/renew').status_code==409
        assert client.post(route+'/return').status_code==200


@pytest.mark.parametrize('question',['Gia hạn sách mẫu thế nào?', 'Tôi muốn trả sách mẫu'])
def test_chat_links_to_demo_circulation_only_when_enabled(tmp_path,monkeypatch,question):
    for enabled in ('true','false'):
        monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS',enabled)
        with TestClient(create_app(tmp_path,testing=True),headers=HEADERS) as client:
            reply=client.post('/api/chat',json={'message':question}).json()
            assert (reply['mode']=='demo_reservation')==(enabled=='true'),reply
            if enabled=='false':
                assert client.get(PATH).status_code==404
                assert client.post(PATH+'/2/checkout').status_code in (404,405)


@pytest.mark.parametrize('question', [QUESTION, 'tôi có thể mượn sách ngay tại đây không ?',
    'Toi co the muon sach qua chatbot khong?', 'Em mượn cuốn này trong đoạn chat này được không?',
    'Mình muốn mượn sách ngay trong khung chat này, được không?',
    'Có đăng ký mượn sách trực tiếp trong chatbot được không?'])
def test_chat_routes_action_to_enabled_demo_and_explains_disabled_mode(tmp_path, monkeypatch, question):
    for enabled in ('true', 'false'):
        monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS', enabled)
        with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
            response = client.post('/api/chat', json={'message': question,
                'history': [{'role':'user','content':'Tìm sách Python'}]}).json()
            assert not response['books']
            assert response['mode'] == ('demo_reservation' if enabled == 'true' else 'faq')
            if enabled == 'false':
                assert client.get(PATH).status_code == 404
                assert 'Đăng ký mượn' in response['answer'] and response['sources']
                if question != QUESTION:
                    assert response['answer'].startswith('Bạn chưa thể mượn sách thật ngay trong chatbot.')
