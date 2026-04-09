# 第4章流程图渲染指南

## 当前项目内情况

经检查，当前仓库的 `package.json` 与 `frontend/package.json` 中均未提供 Mermaid 相关依赖或渲染脚本，也未发现 `mmdc`、`mermaid` 等现成命令。因此，项目内目前没有可直接复用的一键渲染方案。

不过，仓库中已有 `drawio` 图和论文插图文件，可作为后续统一论文配图风格的参考；本次新增的 Mermaid 文件不会覆盖这些已有图示。

## 方案一：使用 Mermaid Live Editor

适用场景：希望快速预览和导出图片，不想配置本地环境。

操作步骤：

1. 打开 Mermaid Live Editor。
2. 将对应 `.md` 文件中的 Mermaid 代码块内容复制进去。
3. 在编辑器中确认排版是否清晰。
4. 导出为 PNG 或 SVG。
5. 将导出的图片按论文需要命名，例如：
   - `parse_chunk_impl_flow.png`
   - `embedding_impl_flow.png`
   - `retrieval_impl_flow.png`
   - `generation_impl_flow.png`
6. 将图片放入论文图片目录，例如 `thesis/figures/chapter4/`。

优点：

- 无需安装依赖。
- 适合快速微调节点文字与布局。

注意：

- 导出前建议将节点文字控制在两行以内，避免论文插图过宽。
- 若导出为 SVG，再转 PNG 时应保持较高分辨率。

## 方案二：本地 Mermaid CLI 渲染

适用场景：希望批量生成图片并保留本地可重复渲染流程。

常用命令形式如下：

```bash
mmdc -i input.mmd -o output.png
```

如果本机未安装 Mermaid CLI，可先安装后再执行。由于当前仓库未内置该依赖，通常需要单独安装 `@mermaid-js/mermaid-cli`。

建议步骤：

1. 将 `.md` 文件中的 Mermaid 代码块内容另存为 `.mmd` 文件，或直接提取代码块。
2. 运行 `mmdc -i xxx.mmd -o xxx.png` 渲染输出。
3. 检查节点是否过满，必要时在 Mermaid 源码中人工换行。
4. 将生成图片复制到论文图片目录。

建议输出文件名：

- `parse_chunk_impl_flow.png`
- `embedding_impl_flow.png`
- `retrieval_impl_flow.png`
- `generation_impl_flow.png`

## 方案三：渲染后再用 Draw.io 或 PPT 微调

适用场景：论文要求图形风格更统一，或需要微调字体、箭头、间距。

建议做法：

1. 先使用 Mermaid 渲染出基础图。
2. 将 PNG 或 SVG 导入 Draw.io、Visio 或 PowerPoint。
3. 统一字体、线宽、节点配色和画布比例。
4. 导出论文最终插图。

这种方式适合毕业论文，因为 Mermaid 负责保证流程逻辑正确，后处理工具负责保证视觉规范。

## 论文插图建议

- 每张图控制在 6 到 9 个核心节点内，当前文件已按这一要求整理。
- 节点优先保留“输入、处理、数据、输出”四类信息，不建议再额外加入异常处理分支。
- 若论文版面较窄，优先导出纵向排布的 `graph TD` 结果。
- 最终插图建议统一宽度为 `0.90\textwidth` 到 `0.95\textwidth`。
