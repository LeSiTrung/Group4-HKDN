import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    data_dir: Path
    testing: bool = False
    secure_cookies: bool = False
    origins: tuple = ('http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8000', 'http://127.0.0.1:8000')

    @classmethod
    def load(cls, data_dir=None, testing=False):
        directory=Path(data_dir or os.getenv('DATA_DIR', str(ROOT/'runtime')))
        if not directory.is_absolute():
            anchored=ROOT/directory
            legacy=Path.cwd()/directory
            if legacy.resolve()!=anchored.resolve() and (legacy/'library.sqlite3').is_file():
                raise RuntimeError('Ambiguous legacy DATA_DIR. Set an absolute path to the existing database before continuing.')
            directory=anchored
        return cls(directory.resolve(), testing,
                   os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
                   tuple(x.strip().rstrip('/') for x in os.getenv('ALLOWED_ORIGINS', ','.join(cls.origins)).split(',') if x.strip()))
