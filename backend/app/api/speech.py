import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=['speech'])
speech_slot = BoundedSemaphore()


class SpeechRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000, strict=True)


@router.post('/speech', response_class=Response)
def speech(payload: SpeechRequest, request: Request):
    model = request.app.state.settings.data_dir / 'tts' / 'vi_VN-vais1000-medium.onnx'
    if not model.is_file() or not model.with_suffix('.onnx.json').is_file():
        raise HTTPException(503, 'Máy chủ chưa cài giọng đọc tiếng Việt.')
    if not speech_slot.acquire(blocking=False):
        raise HTTPException(429, 'Giọng đọc tiếng Việt đang bận. Bạn hãy thử lại sau vài giây.')
    try:
        with TemporaryDirectory() as directory:
            wav_path = Path(directory) / 'speech.wav'
            subprocess.run(
                [sys.executable, '-X', 'utf8', '-m', 'piper', '-m', str(model), '-f', str(wav_path)],
                input=payload.text.encode('utf-8'), capture_output=True, timeout=20, check=True,
            )
            audio = wav_path.read_bytes()
        if len(audio) <= 44:
            raise HTTPException(422, 'Không tìm thấy nội dung có thể đọc thành tiếng.')
        return Response(audio, media_type='audio/wav')
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, 'Chưa tạo được giọng đọc tiếng Việt. Bạn hãy thử lại.') from None
    finally:
        speech_slot.release()
