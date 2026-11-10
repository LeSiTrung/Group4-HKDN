import json

from app.database.connection import Store
from app.services.catalog import BookInput, public_book, save_book
from scripts.collect_opac import digest
from scripts.enrich_opac_marc import apply_marc, stage_marc


def test_marc_import_validates_snapshot_and_preserves_catalog_edits(tmp_path):
    base='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId='
    records=tmp_path/'records'
    records.mkdir()
    marc=[{'tag':'245','value':'__\t$aGiáo trình kho vận /$cTác giả nguồn'},
          {'tag':'650','value':'__\t$aKho vận$xKiểm kê$0https://example.org/id'},
          {'tag':'653','value':'__\t$aTồn kho'},
          {'tag':'520','value':'__\t$aHướng dẫn kiểm kê chu kỳ.'},
          {'tag':'521','value':'__\t$aSinh viên ngành logistics.'},
          {'tag':'856','value':'__\t$uhttps://example.org/private'}]
    for identifier in ('1','2','3','4'):
        record={'id':identifier,'marc':marc}
        snapshot={'record':record,'fetched_at':'2026-10-29T02:00:00+00:00',
                  'source_url':base+identifier,'sha256':digest(record)}
        if identifier=='2':
            snapshot['sha256']='bad'
        if identifier=='3':
            snapshot['fetched_at']='2099-01-01T00:00:00+00:00'
        (records/f'{identifier}.json').write_text(json.dumps(snapshot),encoding='utf-8')
    staged,report=stage_marc(records,{base+identifier for identifier in ('1','2','3')})
    assert report=={'eligible':3,'staged':1,'invalid':2,'missing':0,'empty':0}
    store=Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        book=save_book(db,BookInput(title='Nhan đề đã biên tập',source_url=base+'1',
                                   checked_at='2026-10-28',published=True))
    assert apply_marc(store.connect,staged)==1
    assert apply_marc(store.connect,staged)==0
    assert apply_marc(store.connect,[(base+'1','2026-10-28','b'*64,'Cũ','','')])==0
    found=public_book(store.connect,book['id'])
    assert found['title']=='Nhan đề đã biên tập'
    assert found['marc']=={'subjects':'Kho vận — Kiểm kê; Tồn kho','summary':'Hướng dẫn kiểm kê chu kỳ.',
                           'audience':'Sinh viên ngành logistics.','checked_at':'2026-10-29'}
    with store.connect() as db:
        db.execute('UPDATE books SET source_url=? WHERE id=?',(base+'4',book['id']))
    assert 'marc' not in public_book(store.connect,book['id'])
