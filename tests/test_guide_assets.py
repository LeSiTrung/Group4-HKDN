import mimetypes

from fastapi.testclient import TestClient

from app import main


def test_guide_images_keep_image_media_type_without_windows_mime_registration(tmp_path, monkeypatch):
    mimetypes.init()
    monkeypatch.delitem(mimetypes.types_map, '.webp', raising=False)
    dist=tmp_path/'frontend/dist/assets'
    dist.mkdir(parents=True)
    image=b'RIFF synthetic static media fixture'
    (dist/'guide.webp').write_bytes(image)
    monkeypatch.setattr(main, 'ROOT', tmp_path/'backend')
    client=TestClient(main.create_app(tmp_path/'runtime', testing=True))
    response=client.get('/assets/guide.webp')
    assert response.status_code==200 and response.content==image
    assert response.headers['content-type']=='image/webp'
