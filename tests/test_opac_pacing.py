import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import opac_pacing as pacing


@pytest.fixture
def clock(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    value=[1000.0]
    monkeypatch.setattr(pacing.time,'time',lambda:value[0])
    monkeypatch.setattr(pacing.time,'sleep',lambda seconds:value.__setitem__(0,value[0]+seconds))
    return value


def test_separate_calls_share_persisted_request_spacing(clock):
    pacing.wait_for_turn()
    pacing.wait_for_turn()
    assert clock[0]==1010
    pacing.wait_for_turn(minimum_gap=20)
    assert clock[0]==1020
    pacing.wait_for_turn()
    assert clock[0]==1040
    pacing.wait_for_turn()
    assert clock[0]==1060


def test_busy_gate_has_bounded_wait_without_reserving_future_slots(clock):
    pacing.wait_for_turn(minimum_gap=60)
    with pytest.raises(TimeoutError):
        pacing.wait_for_turn(max_wait=2)
    assert clock[0]==1000
    clock[0]=1060
    pacing.wait_for_turn(max_wait=0)


def test_concurrent_claims_never_share_one_slot(clock):
    def claim(_):
        try:
            pacing.wait_for_turn(max_wait=0)
            return True
        except TimeoutError:
            return False
    with ThreadPoolExecutor(max_workers=4) as workers:
        assert sum(workers.map(claim,range(4)))==1


def test_database_failure_is_closed_instead_of_unpaced_request(clock,monkeypatch):
    monkeypatch.setattr(pacing.sqlite3,'connect',lambda *args,**kwargs:(_ for _ in ()).throw(sqlite3.OperationalError('busy')))
    with pytest.raises(sqlite3.Error):
        pacing.wait_for_turn()


def test_waiting_reader_gets_priority_over_background_collection(clock):
    pacing.wait_for_turn(max_wait=None)
    clock[0]=1001
    pacing.wait_for_turn(max_wait=20)
    assert clock[0]==1010
    pacing.wait_for_turn(max_wait=None)
    assert clock[0]==1021


def test_existing_three_column_clock_is_upgraded_without_losing_spacing(clock):
    path=pacing.Settings.load().data_dir/'opac-pacing.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE request_clock(id INTEGER PRIMARY KEY,next_at REAL NOT NULL,minimum_gap REAL NOT NULL)')
        db.execute('INSERT INTO request_clock VALUES(1,1010,10)')
    with pytest.raises(TimeoutError):
        pacing.wait_for_turn(max_wait=0)
    clock[0]=1010
    pacing.wait_for_turn(max_wait=0)
