# TikZ 顶刊风格示例

以下是 3 个顶刊级别架构图的完整 TikZ 代码，作为风格参考。

## 示例 1: 双分支架构（CVPR/ICCV 风格）

适合：有两条并行处理流、中间分叉汇合的方法。

```latex
\documentclass[border=4pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}
\begin{document}
\begin{tikzpicture}[
  input/.style={draw, rounded corners=2mm, minimum width=2.2cm, minimum height=0.8cm,
                fill=gray!12, draw=gray!50, align=center, font=\sffamily\small},
  innov/.style={draw, rounded corners=2.5mm, minimum width=2.6cm, minimum height=0.95cm,
                fill=blue!18, draw=blue!65!black, line width=1pt, align=center,
                font=\sffamily\small\bfseries},
  proc/.style={draw, rounded corners=2mm, minimum width=2.4cm, minimum height=0.85cm,
               fill=orange!10, draw=orange!50!black, align=center, font=\sffamily\small},
  output/.style={draw, rounded corners=2mm, minimum width=2.2cm, minimum height=0.8cm,
                 fill=green!10, draw=green!50!black, align=center, font=\sffamily\small},
  arr/.style={-{Stealth[length=6pt]}, thick, color=black!65},
  arrd/.style={-{Stealth[length=5pt]}, dashed, color=gray!55},
  gbox/.style={draw=#1, dashed, rounded corners=4pt, inner sep=8pt, line width=0.6pt},
  lbl/.style={font=\sffamily\scriptsize, text=black!45},
]

% Input
\node[input] (input) {Input};

% Split point
\coordinate[right=1.0cm of input] (split);

% Branch A (top)
\node[proc, above right=0.6cm and 1.2cm of split] (procA) {Stream A};
\node[innov, right=1.2cm of procA] (coreA) {\textbf{Core Module A}};

% Branch B (bottom)
\node[proc, below right=0.6cm and 1.2cm of split] (procB) {Stream B};
\node[innov, right=1.2cm of procB] (coreB) {\textbf{Core Module B}};

% Merge point
\coordinate[right=1.0cm of coreA.east] (mergeA);
\coordinate[right=1.0cm of coreB.east] (mergeB);
\coordinate ($(mergeA)!0.5!(mergeB)$) (merge);

% Fusion
\node[innov, right=1.5cm of merge] (fusion) {\textbf{Fusion}};

% Output
\node[output, right=1.2cm of fusion] (output) {Output};

% Arrows - main flow
\draw[arr] (input) -- (split);
\draw[arr] (split) |- (procA);
\draw[arr] (split) |- (procB);
\draw[arr] (procA) -- (coreA);
\draw[arr] (procB) -- (coreB);
\draw[arr] (coreA) -| (fusion);
\draw[arr] (coreB) -| (fusion);
\draw[arr] (fusion) -- (output);

% Grouping
\begin{scope}[on background layer]
  \node[gbox=blue!40, fit=(procA)(coreA),
        label={[lbl]above:Branch A}] {};
  \node[gbox=orange!40, fit=(procB)(coreB),
        label={[lbl]below:Branch B}] {};
\end{scope}

\end{tikzpicture}
\end{document}
```

## 示例 2: 多级流水线（IEEE TIP/TCSVT 风格）

适合：整体框架图，从左到右展示完整 Pipeline。

```latex
\documentclass[border=4pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}
\begin{document}
\begin{tikzpicture}[
  input/.style={draw, rounded corners=2mm, minimum width=2.0cm, minimum height=0.75cm,
                fill=gray!10, draw=gray!45, align=center, font=\sffamily\footnotesize},
  module/.style={draw, rounded corners=2.5mm, minimum width=2.4cm, minimum height=0.9cm,
                 fill=#1, draw=#1!60!black, line width=0.8pt, align=center,
                 font=\sffamily\footnotesize},
  module/.default={blue!12},
  innov/.style={draw, rounded corners=3mm, minimum width=2.6cm, minimum height=1.0cm,
                fill=blue!20, draw=blue!70!black, line width=1.2pt, align=center,
                font=\sffamily\footnotesize\bfseries},
  arr/.style={-{Stealth[length=5pt]}, thick, color=black!55},
  lbl/.style={font=\sffamily\scriptsize, text=black!40, fill=white, inner sep=1pt},
  gbox/.style={draw=black!25, dashed, rounded corners=4pt, inner sep=7pt, line width=0.5pt},
]

% Row 1: Main pipeline
\node[input] (data) {Light Field\\Input};
\node[module={cyan!12}, right=1.3cm of data] (preproc) {Pre-\\processing};
\node[innov, right=1.5cm of preproc] (decomp) {\textbf{Signal}\\[-1pt]\textbf{Decomposition}};
\node[module={orange!12}, right=1.5cm of decomp] (routing) {Feature\\Routing};
\node[innov, right=1.3cm of routing] (dualmask) {\textbf{Dual-Mask}\\[-1pt]\textbf{Fusion}};
\node[input, right=1.3cm of dualmask] (output) {Depth\\Map};

% Row 2: Auxiliary
\node[module={yellow!10}, below=1.2cm of decomp] (labels) {Pseudo-Label\\Generation};
\node[module={green!10}, below=1.2cm of dualmask] (loss) {Mask\\Supervision};

% Main flow arrows
\draw[arr] (data) -- node[lbl, above] {Raw EPIs} (preproc);
\draw[arr] (preproc) -- node[lbl, above] {Features} (decomp);
\draw[arr] (decomp) -- node[lbl, above] {Priors} (routing);
\draw[arr] (routing) -- node[lbl, above] {Branches} (dualmask);
\draw[arr] (dualmask) -- (output);

% Auxiliary arrows
\draw[arr, dashed, color=gray!50] (decomp) -- (labels);
\draw[arr, dashed, color=gray!50] (labels) -| node[lbl, below, pos=0.3] {$\nabla_{ang}$} (loss);
\draw[arr, dashed, color=gray!50] (loss) -- (dualmask);

% Grouping
\node[gbox, fit=(decomp)(labels),
      label={[font=\sffamily\scriptsize, text=blue!50]above left:Physical Prior}] {};
\node[gbox, fit=(routing)(dualmask)(loss),
      label={[font=\sffamily\scriptsize, text=blue!50]above:Adaptive Processing}] {};

\end{tikzpicture}
\end{document}
```

## 示例 3: 模块细节图（单栏，上到下）

适合：展示某个具体模块的内部结构。

```latex
\documentclass[border=4pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}
\begin{document}
\begin{tikzpicture}[
  inp/.style={draw, trapezium, trapezium left angle=70, trapezium right angle=110,
              minimum width=1.8cm, fill=gray!10, draw=gray!45, align=center,
              font=\sffamily\footnotesize},
  layer/.style={draw, rounded corners=2mm, minimum width=3.5cm, minimum height=0.7cm,
                fill=#1, draw=#1!50!black, align=center, font=\sffamily\footnotesize},
  layer/.default={blue!10},
  result/.style={draw, rounded corners=2mm, minimum width=3.5cm, minimum height=0.7cm,
                 fill=green!12, draw=green!50!black, align=center,
                 font=\sffamily\footnotesize},
  arr/.style={-{Stealth[length=5pt]}, thick, color=black!55},
  lbl/.style={font=\sffamily\scriptsize, text=black!40},
]

% Input
\node[inp] (input) {$I(u,v)$};

% Three decomposition outputs
\node[layer={yellow!15}, below left=1.0cm and 0.5cm of input] (dc) {$I_{DC}$\\Ambient};
\node[layer={cyan!15}, below=1.0cm of input] (parallax) {$a \cdot u + b \cdot v$\\Parallax};
\node[layer={orange!15}, below right=1.0cm and 0.5cm of input] (residual) {$\varepsilon(u,v)$\\Material};

% Derived quantities
\node[layer={red!10}, below=0.9cm of parallax] (depth) {$\nabla_{ang}=\sqrt{a^2+b^2}$\\Angular Gradient};
\node[layer={red!10}, below=0.9cm of residual] (var) {$\sigma_\varepsilon^2$\\Residual Var};

% Output
\node[result, below=1.0cm of $(depth)!0.5!(var)$] (output) {Material Classification};

% Arrows
\draw[arr] (input) -- (dc);
\draw[arr] (input) -- (parallax);
\draw[arr] (input) -- (residual);
\draw[arr] (parallax) -- (depth);
\draw[arr] (residual) -- (var);
\draw[arr] (depth) -- (output);
\draw[arr] (var) -- (output);

% Grouping
\node[draw=blue!25, dashed, rounded corners=4pt, inner sep=6pt,
      fit=(dc)(parallax)(residual),
      label={[lbl]above right:OLS Decomposition}] {};

\end{tikzpicture}
\end{document}
```

## 关键风格特征总结

| 元素 | 处理方式 |
|------|----------|
| **创新模块** | `fill=blue!18-20, line width=1-1.2pt, bold font` — 最大最醒目 |
| **普通模块** | `fill=gray!10-12, line width=0.6pt` — 低调存在 |
| **操作/变换** | `fill=orange!10-12` — 介于两者之间 |
| **输入输出** | `fill=gray!10` 或梯形 — 明确标识边界 |
| **主线箭头** | `thick, Stealth[6pt]` — 清晰方向 |
| **辅助箭头** | `dashed, gray` — 不干扰主线 |
| **分组框** | `dashed, rounded corners=4pt, inner sep=8pt` — 柔和包围 |
| **标签** | `\scriptsize\sffamily, text=black!40-50` — 辅助信息低调 |
| **数学公式** | `inline $...$` — 在节点中直接使用 |
