# 数据图 TikZ 生成引导 (v11.0)

> 本文件引导 LLM 在没有真实实验数据/图片时，用 TikZ 生成专业的示意图版本。
> Python = 裁判（编译验证），LLM = 运动员（TikZ 设计），MD = 规则书。

## 1. 消融实验表格 (Ablation Table)

### 模板规范
- 使用 `booktabs` 三线表（`\toprule`, `\midrule`, `\bottomrule`）
- 列数: 方法名 + 2-4 个指标列
- 最后一行是 `Full Model (Ours)`，加粗最佳值
- 每个消融变体移除一个组件

### 示例结构
```
\begin{table}[!t]
\centering
\caption{Ablation study results.}
\label{tab:ablation}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lccc}
\toprule
Method & PSNR (dB) & SSIM & LPIPS \\
\midrule
w/o Component A & 28.5 & 0.892 & 0.156 \\
w/o Component B & 29.1 & 0.908 & 0.142 \\
w/o Component C & 28.8 & 0.895 & 0.151 \\
\textbf{Full Model (Ours)} & \textbf{30.2} & \textbf{0.925} & \textbf{0.118} \\
\bottomrule
\end{tabular}}
\end{table}
```

### 配色规范
- 表头背景: 浅灰 `gray!10`（可选）
- 最佳值: 加粗 `\textbf{}`
- 全模型行: 可用浅蓝背景 `blue!5`

## 2. 性能对比柱状图 (Comparison Bar Chart)

### 模板规范
- 分组柱状图，5-6 个方法 × 2-3 个数据集
- 使用 `pgfplots` 包的 `ybar` 模式
- "Ours" 用醒目颜色（如红色 `red!70!black` 或蓝色 `blue!80`）
- 包含图例、坐标轴标签

### 示例结构
```
\begin{figure}[!t]
\centering
\begin{tikzpicture}
\begin{axis}[
    ybar,
    bar width=8pt,
    width=0.48\textwidth,
    height=5cm,
    symbolic x coords={HCI, Lytro, Synthetic},
    xtick=data,
    ylabel={PSNR (dB)},
    ymin=25, ymax=35,
    legend style={at={(0.5,-0.2)}, anchor=north, legend columns=3, font=\small},
    enlarge x limits=0.2,
]
\addplot coordinates {(HCI,28.1) (Lytro,27.5) (Synthetic,29.8)};
\addplot coordinates {(HCI,29.3) (Lytro,28.2) (Synthetic,30.5)};
\addplot coordinates {(HCI,30.2) (Lytro,29.8) (Synthetic,31.4)};
\legend{Method A, Method B, \textbf{Ours}}
\end{axis}
\end{tikzpicture}
\caption{Performance comparison on benchmark datasets.}
\label{fig:comparison}
\end{figure}
```

### 配色方案
- Method A: `blue!60`
- Method B: `green!60`  
- Method C: `orange!60`
- Ours: `red!80` + 加粗

## 3. 定性对比图 (Qualitative Comparison)

### 模板规范
- 网格布局：行 = 不同场景，列 = 不同方法
- 使用 `\tikz\node` 创建带标签的占位框
- 每个框标注描述性标签（如 "Input", "Method A", "Ours", "GT"）
- 箭头表示处理流程

### 示例结构
```
\begin{figure*}[!t]
\centering
\begin{tikzpicture}[
    imgbox/.style={draw, minimum width=2.5cm, minimum height=2cm, 
                   inner sep=0pt, font=\small},
]
% Row 1
\node[imgbox] (a1) at (0,0) {Scene 1\\Input};
\node[imgbox] (a2) at (3.2,0) {Method A};
\node[imgbox] (a3) at (6.4,0) {Method B};
\node[imgbox, line width=1.5pt, draw=red!70!black] (a4) at (9.6,0) {\textbf{Ours}};
\node[imgbox] (a5) at (12.8,0) {Ground Truth};

% Row 2
\node[imgbox] at (0,-2.8) {Scene 2\\Input};
...

% Column labels
\node[above=2pt] at (a1.north) {\footnotesize Input};
...
\end{tikzpicture}
\caption{Qualitative comparison of different methods.}
\end{figure*}
```

## 4. 通用规则

### 占位数据规则
- **必须**使用合理的占位数值（不是 xxx 或 ???）
- PSNR 范围: 25-35 dB
- SSIM 范围: 0.85-0.95
- LPIPS 范围: 0.05-0.20
- "Ours" 方法的数值应该最好

### 尺寸规范
- 单栏图: `width=\columnwidth` 或 `width=8cm`
- 双栏图: `width=\textwidth` 或 `width=16cm`
- 表格高度: ≤ 6cm
- 柱状图高度: 4-6cm

### 编译兼容性
- 只使用 `tikz`, `pgfplots`, `booktabs`, `amsmath` 等标准包
- 不使用 `tikz` 的外部库（除了 `pgfplots` 自带的）
- 所有 `\begin{...}` 和 `\end{...}` 必须配对
- 不用中文字符
