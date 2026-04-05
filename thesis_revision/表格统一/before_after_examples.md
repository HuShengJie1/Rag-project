# 代表性表格前后对比示例

本文件选取 4 张代表性表格，概述本次统一前后的样式差异，便于快速检查修改效果。以下“修改前”描述基于本次任务开始时的审计结果，“修改后”描述基于当前 [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex)。

## 示例 1：OmniDocBench 外部基准表

- 位置：
  - [毕业论文.tex:356](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L356)
- 表题：
  - “代表性解析模型/工具在 OmniDocBench v1.5 的多维度端到端性能对比”

修改前关键写法：

```tex
\resizebox{\textwidth}{!}{%
\begin{tabular}{llcccccc}
...
\end{tabular}
}
\vspace{1ex}
\par\raggedright\small\textit{注：...}
```

修改后关键写法：

```tex
{\small
\renewcommand{\arraystretch}{1.2}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{llcccccc}
...
\end{tabular}
\end{adjustbox}
}
\thesistablenote{...}
```

变化说明：

1. 固定缩放改为“仅超宽时缩放”。
2. 显式统一表内字号与行距。
3. 注释从手工内联改为统一宏。

## 示例 2：第 4 章本地对比表

- 位置：
  - [毕业论文.tex:445](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L445)
- 表题：
  - “同一工程认证文档在不同解析方案下的本地对比结果”

修改前关键写法：

```tex
\caption{...}
\label{...}
\renewcommand{\arraystretch}{1.2}
\resizebox{\textwidth}{!}{%
\begin{tabular}{p{...}...}
```

修改后关键写法：

```tex
\caption{...}
\label{...}
{\small
\renewcommand{\arraystretch}{1.2}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{p{...}...}
```

变化说明：

1. 保留原有 `arraystretch` 的基础上，补齐统一字号。
2. 将缩放方式统一到全文标准。
3. caption 与 label 顺序保持不变，与全文一致。

## 示例 3：榜单参考表

- 位置：
  - [毕业论文.tex:518](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L518)
- 表题：
  - “主流开源中文向量模型检索性能对比（用于榜单参考）”

修改前关键写法：

```tex
\resizebox{\textwidth}{!}{%
\begin{tabular}{llccc}
...
\end{tabular}%
}
\par\raggedright\small\textit{注：...}
```

修改后关键写法：

```tex
{\small
\renewcommand{\arraystretch}{1.2}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{llccc}
...
\end{tabular}
\end{adjustbox}
}
\thesistablenote{...}
```

变化说明：

1. 表格主体和注释都并入统一模板。
2. 表后注释风格与前一张注释表完全一致。

## 示例 4：窄表性能结果表

- 位置：
  - [毕业论文.tex:1041](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L1041)
- 表题：
  - “不同系统配置下的检索性能对比”

修改前关键写法：

```tex
\resizebox{\textwidth}{!}{
\begin{tabular}{lccc}
...
\end{tabular}
}
```

修改后关键写法：

```tex
{\small
\renewcommand{\arraystretch}{1.2}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccc}
...
\end{tabular}
\end{adjustbox}
}
```

变化说明：

1. 这类本身并不宽的表，修改前会被强行拉伸到整页宽；
2. 修改后只在超宽时缩放，因此更有利于保持与其他表一致的实际字号。
