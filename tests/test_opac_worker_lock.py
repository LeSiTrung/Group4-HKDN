from runpy import run_path
from pathlib import Path

import pytest

module=run_path(str(Path(__file__).resolve().parents[1]/'scripts/collect_opac.py'))


def test_one_collector_per_output_directory_and_release_on_failure(tmp_path):
    with pytest.raises(ValueError,match='test failure'):
        with module['collection_lock'](tmp_path):
            with pytest.raises(RuntimeError,match='already running'):
                with module['collection_lock'](tmp_path):
                    pytest.fail('Duplicate worker obtained output lock')
            with module['collection_lock'](tmp_path/'other'):
                pass
            raise ValueError('test failure')
    with module['collection_lock'](tmp_path):
        pass
