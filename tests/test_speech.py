from fastapi.testclient import TestClient

from app.main import create_app


def test_speech_uses_local_vietnamese_model(tmp_path,monkeypatch):
    import subprocess
    from pathlib import Path

    model=tmp_path/'tts'/'vi_VN-vais1000-medium.onnx'
    model.parent.mkdir()
    model.touch()
    model.with_suffix('.onnx.json').touch()
    text='Bạn có thể tra cứu tài liệu tại thư viện.'

    def synthesize(command,**options):
        assert command[1:4]==['-X','utf8','-m'] and command[4]=='piper'
        assert str(model) in command
        assert options['input']==text.encode('utf-8') and options['timeout']==20
        Path(command[-1]).write_bytes(b'RIFF0000WAVE'+bytes(40))

    with TestClient(create_app(tmp_path,testing=True)) as client:
        monkeypatch.setattr(subprocess,'run',synthesize)
        headers={'X-Requested-With':'LibraryAssistant'}
        response=client.post('/api/speech',json={'text':text},headers=headers)
        assert response.status_code==200 and response.headers['content-type']=='audio/wav'
        assert response.content.startswith(b'RIFF')
        assert client.post('/api/speech',json={'text':text}).status_code==403
        assert client.post('/api/speech',json={'text':' '*3},headers=headers).status_code==422
        assert client.post('/api/speech',json={'text':'a'*4001},headers=headers).status_code==422


def test_speech_unavailable_without_model(tmp_path):
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        response=client.post('/api/speech',json={'text':'Thư viện UTH'})
        assert response.status_code==503 and 'giọng đọc tiếng Việt' in response.json()['detail']
