# Local embedding export evidence — 2026-10-31

`EXPORT-01` exported the already trained `training/runtime/uth-minilm-2026-10-31/final` checkpoint without retraining, publishing, changing the backend environment, or changing the serving model. The artifacts and model weights remain ignored local files.

## Reproduce in the isolated CPU environment

From the repository root on Windows amd64, CPython 3.11.17:

```powershell
training\.venv\Scripts\python.exe -m venv training\export\.venv
training\export\.venv\Scripts\python.exe -m pip install --require-hashes -r training\requirements-export-lock.txt
training\export\.venv\Scripts\python.exe -m pip check
training\export\.venv\Scripts\python.exe training\export_onnx.py --run training\runtime\uth-minilm-2026-10-31 --dataset training\runtime\dataset-2026-10-31 --reference-python training\.venv\Scripts\python.exe --fastembed-python backend\.venv\Scripts\python.exe
```

The last command intentionally refuses an existing `onnx/` directory or `onnx-parity.json`; preserve an evaluated export. The reference interpreter must match the torch, SentenceTransformers and Transformers versions recorded in the training metrics. The optional FastEmbed interpreter loads the local export offline in a separate process; it does not open the catalog database or modify backend configuration. Other platforms need a new resolved wheel lock.

The isolated exporter uses PyTorch **2.11.0+cpu**, SentenceTransformers **6.2.0**, Transformers **5.22.1**, ONNX **1.23.2**, ONNX Runtime **1.31.1**, NumPy **2.4.6**. The original training runtime remains torch **2.11.0+cu128**, SentenceTransformers **6.2.0**, Transformers **5.22.1**. Every encoder runs on CPU with at most four intra-op/BLAS threads. `requirements-export-lock.txt` pins 47 packages to the resolved Windows wheel SHA-256 values, including the existing venv setuptools version.

No Optimum package or incompatible dependency bypass is needed. The script uses the documented [PyTorch ONNX exporter](https://github.com/pytorch/pytorch/blob/v2.11.0/docs/source/onnx.md), with the explicitly selected legacy exporter and opset 17. Its legacy/tracing warnings are retained: validation covers this checkpoint and the measured input shapes, not every architecture or arbitrary ONNX input. Upgrade this path when a supported Optimum/Transformers combination is available and recheck parity.

## Measured results

All results below were actually measured on 2026-10-31. The independent reference process loads the same local checkpoint in the original training environment. The export process verifies all nine source files by SHA-256 before and after export, identical tokenizer tensors, and the actual transformer plus mean-pooling configuration. Tokenizer/config files are copied byte for byte.

| Comparison with original normalized FP32 reference | Maximum absolute error | Minimum cosine | Result |
| --- | ---: | ---: | --- |
| Isolated CPU PyTorch, same ST/Transformers versions | 0 | 0.9999998808 | PASS |
| ONNX Runtime CPU, batch sizes 1, 3 and 8 | 0.000000301749 | 0.9999999404 | PASS for each batch size |
| FastEmbed 0.9.1 CPU, local custom-model registration, batch size 8 | 0.000000309199 | 0.9999998808 | PASS |

The frozen 50 inputs comprise 16 development queries, 16 public-metadata document texts, Vietnamese with/without accents, decomposed Unicode, emoji, Chinese/Japanese/Arabic, whitespace/empty input, an instruction-like string, and repeated words around and beyond the truncation boundary. Actual token lengths span **2–128**, including **126, 127, 128**. Every comparison returns a finite normalized **float32 [50,384]** matrix. The acceptance gates are max absolute error `<0.001`, minimum cosine `>0.999`, matching shapes/dtypes and unit norms. These inputs test numerical conversion, not relevance or prompt-injection defenses.

The ONNX graph returns `last_hidden_state`, with dynamic batch and sequence axes. Consumers must apply the bundled tokenizer with the explicit **128-token limit**, attention-mask mean pooling, then L2 normalization. The FastEmbed check registers those exact settings and loads `specific_model_path` with `local_files_only=True`, `CPUExecutionProvider`, `cuda=False`. This proves local FastEmbed tensor parity; application registration, vector reindexing and serving promotion are separate work.

Local evidence:

- `training/runtime/uth-minilm-2026-10-31/onnx-parity.json`: full results, package versions, source/output hashes, all inputs and token lengths.
- `training/runtime/uth-minilm-2026-10-31/onnx/reference.npz`: original embedding/token tensors; `reference.json`: original runtime provenance.
- `training/runtime/uth-minilm-2026-10-31/onnx/model/`: ONNX plus identical source config/tokenizer files. ONNX size: **470,235,032 bytes**.
- `training/runtime/export-install-report.json`: resolved wheel URLs/hashes; `export-lock-resolved.json`: successful `pip --dry-run --ignore-installed --require-hashes` resolution, with `export-lock-check.log`.

| Artifact | SHA-256 |
| --- | --- |
| Original `final/model.safetensors` | `23c1cf9e81512ae54560705410c3004bc7fe5758479856706235b2a0228e0587` |
| Exported `onnx/model/model.onnx` | `64d95cfeb94572d9a85ce68ab64b380f6aec6923cbd883a58aebeea817cd2a52` |
| Tokenizer, unchanged | `cad551d5600a84242d0973327029452a1e3672ba6313c2a3c3d69c4310e12719` |
| Frozen training dataset manifest | `94e5dcfc4432a7afecbb1c9352b6dba2115712c4d493aaea850e6808c089e65a` |

## Checks and remaining limits

`backend\.venv\Scripts\python.exe -m pytest tests/test_embedding_export.py tests/test_training_data.py -q` passed **26 tests**. The checks reject a smoke/non-WIN/non-finite candidate, altered frozen dataset or checkpoint, and mismatched/non-finite/non-FP32/non-normalized embeddings. Export also fails closed if the requested reference runtime, tokenizer, ONNX or FastEmbed comparison differs; unsuccessful staging directories are not promoted to `onnx/`. `pip check` passed and hash-locked resolution passed without forcing dependencies.

No production configuration, database, model cache used by the API, historical metrics, or original model weights were changed. The historical training metrics did not contain a checkpoint weight hash; the recorded source hash identifies the checkpoint at export time and verifies its stability during this run. Tensor parity does not establish staff-reviewed search relevance, improve the synthetic training verdict, verify vector-index migration, or justify production promotion. Keep the serving baseline until those acceptance gates pass.
