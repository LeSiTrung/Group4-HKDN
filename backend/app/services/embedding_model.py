"""Load only the local export whose runtime parity and assets were verified."""
import hashlib
import json
import math
from pathlib import Path


def _parity_passed(value):
    if not isinstance(value,dict):
        return False
    error,cosine=value.get('max_abs_error'),value.get('min_cosine')
    shape=value.get('embedding_shape')
    return (value.get('passed') is True and value.get('dtype')=='float32'
        and isinstance(shape,list) and len(shape)==2 and type(shape[0]) is int and shape[0]>0 and shape[1]==384
        and type(error) in (int,float) and math.isfinite(error) and 0<=error<1e-3
        and type(cosine) in (int,float) and math.isfinite(cosine) and 0.999<cosine<=1.00001)


def verify_assets(directory,expected):
    try:
        if {path.name for path in directory.iterdir()}!=set(expected):
            raise ValueError
        for name,digest in expected.items():
            with (directory/name).open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:
                    raise ValueError
    except (OSError,ValueError):
        raise ValueError('Invalid embedding export assets') from None


def verified_export(path):
    try:
        report_path=Path(path).resolve()
        report=json.loads(report_path.read_text(encoding='utf-8'))
        if (report.get('passed') is not True or report.get('max_seq_length')!=128
            or report.get('pooling')!='attention-mask mean' or report.get('normalized') is not True
            or not _parity_passed(report.get('fastembed'))
            or not isinstance(report.get('onnx_batches'),list) or not report['onnx_batches']
            or not all(_parity_passed(row) for row in report['onnx_batches'])):
            raise ValueError
        hashes=report['artifact_sha256']
        if not isinstance(hashes,dict) or set(hashes)!={'model.onnx','config.json','tokenizer.json','tokenizer_config.json'}:
            raise ValueError
        if any(not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value) for value in hashes.values()):
            raise ValueError
        directory=report_path.parent/'onnx'/'model'
        verify_assets(directory,hashes)
        config=json.loads((directory/'config.json').read_text(encoding='utf-8'))
        tokenizer=json.loads((directory/'tokenizer_config.json').read_text(encoding='utf-8'))
        tokens=json.loads((directory/'tokenizer.json').read_text(encoding='utf-8'))
        if config.get('hidden_size')!=384 or tokenizer.get('model_max_length')!=128 or tokens.get('truncation',{}).get('max_length')!=128:
            raise ValueError
    except (OSError,ValueError,KeyError,TypeError,AttributeError,RecursionError):
        raise ValueError('Invalid embedding export report or assets') from None
    identity=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'name':'local/uth-minilm-'+identity,'directory':directory,'hashes':hashes}


def load_local_model(export):
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource,PoolingType
    verify_assets(export['directory'],export['hashes'])
    if not any(row['model']==export['name'] for row in TextEmbedding.list_supported_models()):
        TextEmbedding.add_custom_model(model=export['name'],pooling=PoolingType.MEAN,normalization=True,
            sources=ModelSource(hf='local/unused-offline'),dim=384,model_file='model.onnx',output_name='last_hidden_state')
    return TextEmbedding(model_name=export['name'],specific_model_path=str(export['directory']),
        local_files_only=True,threads=2,providers=['CPUExecutionProvider'],cuda=False)
