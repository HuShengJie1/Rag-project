# MinerU 批量解析（解析阶段）

该目录用于制度文件解析实验，只负责将源文件交给 MinerU 并生成结构化结果目录与 manifest，不包含 embedding、切块或检索评测。

## 目录建议

- `run_mineru_batch.py`: 批处理入口
- `file_discovery.py`: 文件扫描与过滤
- `mineru_runner.py`: MinerU CLI 封装（`subprocess`）
- `manifest.py`: 解析结果清单导出（CSV/JSON）
- `logging_utils.py`: 控制台+文件日志
- `input_docs/`: 输入文件目录
- `outputs/`: 每个文件的独立输出目录
- `logs/`: 运行日志

## 最小可运行命令

```bash
python experiments/embedding_experiment/parsing/run_mineru_batch.py \
  --input_dir experiments/embedding_experiment/parsing/input_docs \
  --output_dir experiments/embedding_experiment/parsing/outputs \
  --backend pipeline \
  --manifest experiments/embedding_experiment/parsing/manifest.csv
```

## 双版本运行（Pipeline + VLM）

```bash
python3 experiments/embedding_experiment/parsing/run_mineru_dual.py \
  --input_dir /Users/user/毕设/rag-project/data/system_docs \
  --output_root experiments/embedding_experiment/parsing/outputs \
  --manifest_root experiments/embedding_experiment/parsing \
  --mineru_bin .venv/bin/mineru \
  --hf_cache_dir models/hf_cache/hub \
  --retries 1
```

输出将分开保存：

- `outputs/pipeline/*`
- `outputs/vlm/*`
- `manifest.pipeline.csv/json`
- `manifest.vlm.csv/json`
- `manifest.dual.csv/json`（两版合并）

## 单文件模式

```bash
python experiments/embedding_experiment/parsing/run_mineru_batch.py \
  --input_file /path/to/one.pdf \
  --output_dir experiments/embedding_experiment/parsing/outputs \
  --backend pipeline \
  --manifest experiments/embedding_experiment/parsing/manifest.csv
```

## 常用参数

- `--backend {auto,pipeline}`: `pipeline` 用于 CPU fallback
- `--dry_run`: 仅生成计划与 manifest，不执行 MinerU
- `--retries N`: 单文件失败重试次数
- `--input_file <path>`: 单文件解析模式（与 `--input_dir` 二选一）
- `--include_docx`: 额外包含 `.docx`
- `--include_images`: 额外包含图片（`.png/.jpg/...`）
- `--skip_existing/--no-skip_existing`: 是否跳过已有输出目录
- `--manifest_json <path>`: 额外导出 JSON 清单
- `--hf_cache_dir <path>`: 本地 HF 缓存目录（通常传 `.../hub`）
- `--mineru_bin <bin>`: 指定 MinerU 可执行文件路径

## MinerU 调用方式

- 默认：`mineru -p <input> -o <output>`
- CPU fallback：`mineru -p <input> -o <output> -b pipeline`

## Manifest 关键字段

- `file_id`, `file_name`, `absolute_path`, `relative_path`, `file_type`
- `run_profile`（`single/pipeline/vlm`）
- `parse_status`（`success/failed/skipped`）
- `output_dir`, `error_message`, `parsed_at`
- Markdown 产物：`output_md_exists`, `output_md_path`
- 额外保留：`backend`, `attempts`, `duration_ms`, `file_size_bytes`, `modified_time`, `source_hash`, `command`
