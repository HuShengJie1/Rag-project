#!/usr/bin/env bash
set -euo pipefail

# 4.1 章本地解析对比入口脚本。
# 默认行为：
# 1. 复用项目内既有的 MinerU pipeline / VLM 解析结果；
# 2. 使用 pdftotext 生成弱基线文本；
# 3. 在 experiment/4.1章/generated/ 下整理页级片段与索引。
#
# 如本机缺少 pdftotext，请先安装 poppler；脚本不会自动修改项目其他目录。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "未找到可用的 Python 解释器: ${PYTHON_BIN}" >&2
  exit 1
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/run_compare.py" "$@"
