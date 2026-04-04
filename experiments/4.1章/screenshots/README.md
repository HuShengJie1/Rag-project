# 4.1 章截图页面说明

本目录用于生成论文第 4.1 章“复杂结构文档解析与精细化切块策略”的本地对比截图页面。所有页面均基于项目中的真实 PDF、真实 `pdftotext -layout` 输出以及真实 MinerU 解析结果整理而成。

## 一、对应论文插图

### 1. `parser_matrix_compare.html`

- 对应论文图：
  - 图 A：培养方案第 2 页“毕业要求支撑矩阵”本地解析对比。
- 页面内容：
  - 原始 PDF 页面局部；
  - `pdftotext -layout`；
  - `MinerU pipeline`；
  - `MinerU2.5`。
- 建议截图方式：
  - 直接打开整个页面后，截取四列完整区域即可。
  - 若论文版面较窄，可只保留标题与四列卡片，不保留浏览器地址栏。
- 建议表达重点：
  - `pdftotext -layout` 将矩阵线性化；
  - `MinerU pipeline` 恢复表格外形但局部符号有误；
  - `MinerU2.5` 能较完整保留矩阵结构与勾选关系。

### 1'. `parser_matrix_compare.md`

- 用途：
  - 与 `parser_matrix_compare.html` 对应的 Markdown 版。
- 适用场景：
  - 当你希望在支持数学公式的 Markdown 预览器中打开，并保留后续扩展公式展示能力时，优先使用该文件。
- 说明：
  - 当前该页本身不以公式为主，但 Markdown 版更适合与第 2 个页面统一预览方式。

### 2. `parser_mixed_compare.html`

- 对应论文图：
  - 图 B：制度办法复杂页面本地解析对比。
- 页面内容：
  - 第 1 行：制度办法第 1 页，原始页 / `pdftotext -layout` / `MinerU2.5`；
  - 第 2 行：制度办法第 4 页，原始页 / `MinerU pipeline` / `MinerU2.5`。
- 建议截图方式：
  - 若论文允许较大图片，建议直接截取整个页面，保留两行对比；
  - 若论文需要拆分，也可单独截取第 1 行或第 2 行，其中第 2 行更适合突出公式与表格混排差异。
- 建议表达重点：
  - 第 1 行突出扫描型页面下弱基线为空输出；
  - 第 2 行突出 pipeline 公式失真，而 `MinerU2.5` 同时保留表格与公式语义。

### 2'. `parser_mixed_compare.md`

- 用途：
  - 与 `parser_mixed_compare.html` 对应的 Markdown 版。
- 适用场景：
  - 当你希望公式以 `$$...$$` 数学块形式渲染时，优先使用该文件。
- 说明：
  - `MinerU2.5` 的公式片段已直接保留为数学块；
  - `MinerU pipeline` 的公式失真较明显，为避免无效渲染影响阅读，保留为原始 LaTeX 文本代码块。

## 二、建议打开方式

建议直接在桌面浏览器中打开以下文件：

1. `experiments/4.1章/screenshots/parser_matrix_compare.html`
2. `experiments/4.1章/screenshots/parser_mixed_compare.html`

页面已经使用统一宽度、白底黑字、细边框与等宽字体排版，打开后无需再手动调整布局即可截图。

如果你更关注公式渲染，而不是并排截图版式，可改为打开以下 Markdown 文件并使用支持数学公式的预览器：

1. `experiments/4.1章/screenshots/parser_matrix_compare.md`
2. `experiments/4.1章/screenshots/parser_mixed_compare.md`

## 三、目录内关键文件

- `style.css`
  - 两个 HTML 共用样式。
- `assets/`
  - 存放从原始 PDF 实际导出的页面 PNG。
- `data/render_index.json`
  - 记录 HTML 页面所使用的真实来源文件路径。
- `build_compare.py`
  - 自动生成 HTML 页面与原始页图片的脚本。

## 四、真实缺失项说明

1. 制度办法第 1 页的 `pdftotext -layout` 输出真实为空。
   - 在页面中已明确标注为“缺失：未获得可用输出”，未进行编造。
2. `parser_mixed_compare.html` 的第 1 行未放入 `MinerU pipeline`。
   - 这是按当前论文展示目标进行压缩布局后的选择，不代表该页没有 pipeline 结果。
   - 本次页面重点是突出扫描页在弱基线下失效，以及最终方案 `MinerU2.5` 的结构恢复能力。
3. `parser_mixed_compare.html` 的第 2 行未放入 `pdftotext -layout`。
   - 这是按既定展示结构保留“原始页 / pipeline / MinerU2.5”的三栏对比，以便更集中展示公式失真问题。

## 五、如果后续需要重新生成

执行以下命令即可在当前目录重新生成图片和 HTML：

```bash
python3 experiments/4.1章/screenshots/build_compare.py
```
