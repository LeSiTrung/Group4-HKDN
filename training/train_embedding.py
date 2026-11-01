"""One local, bounded bi-encoder run; adapted from the SentenceTransformers skill template.

Publications and production promotion are deliberately outside this script.
"""
import argparse
import hashlib
import json
import logging
import os
import platform
import time
from contextlib import nullcontext
from importlib.metadata import version
from pathlib import Path

os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'

import torch
from datasets import Dataset
from sentence_transformers import (SentenceTransformer, SentenceTransformerModelCardData,
    SentenceTransformerTrainer, SentenceTransformerTrainingArguments)
from sentence_transformers.sentence_transformer.evaluation import InformationRetrievalEvaluator
from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
from sentence_transformers.sentence_transformer.training_args import BatchSamplers
from sentence_transformers.util import cos_sim
from transformers import set_seed
from prepare_data import load_frozen_dataset

BASE_MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
SEED=31


def autocast_ctx():
    if not torch.cuda.is_available():
        return nullcontext()
    return torch.autocast('cuda',dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)


def setup_logging(output):
    (output/'logs').mkdir(parents=True,exist_ok=True)
    logging.basicConfig(format='%(asctime)s - %(message)s',level=logging.INFO,
        handlers=[logging.StreamHandler(),logging.FileHandler(output/'logs/uth-multilingual-minilm.log',encoding='utf-8')],force=True)
    for noisy in ('httpx','httpcore','httpx2','httpcore2','huggingface_hub','urllib3','filelock','fsspec'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    torch.set_float32_matmul_precision('high')


def evaluator_for(name,rows,documents):
    return InformationRetrievalEvaluator(
        queries={row['group_id']:row['query'] for row in rows},
        corpus={identifier:row['text'] for identifier,row in documents.items()},
        relevant_docs={row['group_id']:set(row['relevant_ids']) for row in rows},
        name=name,mrr_at_k=[5],ndcg_at_k=[5],accuracy_at_k=[1,5],
        precision_recall_at_k=[5],map_at_k=[5],show_progress_bar=False,
        batch_size=16,corpus_chunk_size=2000,score_functions={'cosine':cos_sim})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    if (args.output/'metrics.json').exists() or (args.output/'checkpoints').exists():
        parser.error('Training output already exists; choose a new output directory.')
    setup_logging(args.output)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; refusing an unbounded CPU training run.')
    set_seed(SEED)
    torch.set_num_threads(4)
    manifest,documents,splits=load_frozen_dataset(args.dataset)
    if args.smoke:
        splits={name:rows[:min(len(rows),16)] for name,rows in splits.items()}
        needed={identifier for rows in splits.values() for row in rows for identifier in row['relevant_ids']}
        needed.update(list(documents)[:32])
        documents={key:value for key,value in documents.items() if key in needed}
    model=SentenceTransformer(BASE_MODEL,device='cuda',model_card_data=SentenceTransformerModelCardData(
        language='vi',license='apache-2.0',model_name='UTH library metadata retrieval experiment'))
    model.max_seq_length=128
    dev=evaluator_for('uth-dev',splits['dev'],documents)
    test=evaluator_for('uth-test',splits['test'],documents)
    logging.info('BASELINE dev/test evaluation; documents=%s train=%s dev=%s test=%s',len(documents),len(splits['train']),len(splits['dev']),len(splits['test']))
    started=time.perf_counter()
    with autocast_ctx():
        baseline_dev=dev(model)
        baseline_test=test(model)
    baseline_eval=baseline_dev[dev.primary_metric]
    metric_key=f'eval_{dev.primary_metric}'
    logging.info('Baseline primary metric %s=%s',dev.primary_metric,baseline_eval)
    train_dataset=Dataset.from_list([{'anchor':row['query'],'positive':row['positive']} for row in splits['train']])
    eval_dataset=Dataset.from_list([{'anchor':row['query'],'positive':row['positive']} for row in splits['dev']])
    steps=1 if args.smoke else min(300,max(1,len(train_dataset)//8))
    interval=1 if args.smoke else max(1,steps//3)
    training_args=SentenceTransformerTrainingArguments(
        output_dir=str(args.output/'checkpoints'),num_train_epochs=1,max_steps=steps,
        per_device_train_batch_size=8,per_device_eval_batch_size=8,learning_rate=2e-5,
        warmup_steps=0.1,weight_decay=0.01,lr_scheduler_type='linear',
        bf16=torch.cuda.is_bf16_supported(),fp16=not torch.cuda.is_bf16_supported(),
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_strategy='steps',eval_steps=interval,save_strategy='steps',save_steps=interval,
        save_total_limit=2,logging_steps=10 if not args.smoke else 1,logging_first_step=True,
        load_best_model_at_end=True,metric_for_best_model=metric_key,greater_is_better=True,
        report_to='none',push_to_hub=False,run_name='uth-multilingual-minilm',seed=SEED,
        dataloader_num_workers=0,dataloader_pin_memory=True)
    trainer=SentenceTransformerTrainer(model=model,args=training_args,train_dataset=train_dataset,
        eval_dataset=eval_dataset,loss=MultipleNegativesRankingLoss(model),evaluator=dev)
    trainer.train()
    with autocast_ctx():
        final_dev=dev(model)
        final_test=test(model)
    # Checkpoint selection uses dev only; the frozen test supplies the final comparison.
    baseline=baseline_test[test.primary_metric]
    score=final_test[test.primary_metric]
    delta=score-baseline
    verdict='WIN' if delta>=0.005 else 'MARGINAL' if delta>=0 else 'REGRESSION'
    model.save_pretrained(args.output/'final')
    config=model[0].auto_model.config
    report={'kind':'synthetic public-metadata retrieval experiment; not human library acceptance',
        'smoke':args.smoke,'base_model':BASE_MODEL,'base_revision':getattr(config,'_commit_hash',None),
        'seed':SEED,'max_seq_length':128,'training_steps':trainer.state.global_step,
        'best_checkpoint':trainer.state.best_model_checkpoint,'selection_metric':metric_key,
        'baseline_dev':baseline_dev,'baseline_test':baseline_test,'final_dev':final_dev,'final_test':final_test,
        'verdict':verdict,'test_primary_metric':test.primary_metric,'baseline':baseline,'score':score,'delta':delta,
        'elapsed_seconds':round(time.perf_counter()-started,2),
        'hardware':{'gpu':torch.cuda.get_device_name(0),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'cuda':torch.version.cuda,'python':platform.python_version()},
        'packages':{package:version(package) for package in ('torch','sentence-transformers','transformers','datasets','accelerate')},
        'dataset_manifest_sha256':hashlib.sha256((args.dataset/'manifest.json').read_bytes()).hexdigest(),
        'dataset':manifest,'promotion_status':'not deployed; ONNX/FastEmbed export, runtime parity and staff-reviewed held-out evaluation still required',
        'publication':'No Hub push or external tracker; local artifacts only'}
    (args.output/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (args.output/'logs/experiments.md').open('a',encoding='utf-8') as ledger:
        ledger.write(f'\n- {verdict}: baseline={baseline:.6f}, score={score:.6f}, delta={delta:+.6f}; synthetic grouped metadata retrieval; no production promotion.\n')
    logging.info('VERDICT: %s | score=%.6f | baseline=%.6f | delta=%+.6f',verdict,score,baseline,delta)


if __name__=='__main__':
    main()
