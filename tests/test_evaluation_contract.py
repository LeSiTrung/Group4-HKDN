from pathlib import Path
from runpy import run_path


def test_evaluation_rejects_wrong_answer_provenance_mode():
    check=run_path(str(Path(__file__).resolve().parents[1]/'scripts/evaluate.py'))['failures']
    case={'status':'answered','mode':'rag'}
    assert check(case,{'status':'answered','answer':'A response','mode':'faq'})
    assert not check(case,{'status':'answered','answer':'A response','mode':'rag'})
