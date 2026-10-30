# Review classifier: baseline V0

## 这轮做什么

只用已固定的 81 条 Dev 评论运行 policy-only baseline。21 条 Test 没有放进此文件夹。
不加入 few-shot 示例、不根据人工标签改写政策、不开展第二轮优化。
政策来自你提供的完整版本，只统一了标点和排版。
调用为独立请求，上一条评论和模型回答不会进入下一条。

## Windows / VS Code / Anaconda 运行

1. 解压整个文件夹。不要只取 classifier.py。
2. 在这个文件夹打开终端，或进入该目录。
3. 执行：

```powershell
python classifier.py --dry-run
python classifier.py
```

按提示填写 provider、模型 ID、API key。provider 选 openai、anthropic 或 compatible。
模型必须填你账号可用的 API 模型 ID，不是网页显示名称。
API key 隐藏输入，不保存。不要把 key 发到聊天、表格或共享文件里。
兼容服务需要填写完整 HTTPS Chat Completions 接口地址。
Python 3.10+ 即可，不需要 pip 安装或 GPU。

注意：代码在电脑运行，评论会发送给选择的云端 API。API 需要可用额度，81 条会产生调用费用。

## 在 Jupyter 中运行

把 notebook 放在解压后的文件夹，执行以下单元格。API key 提示在单元格输出里输入。

```python
%run classifier.py --dry-run
%run classifier.py
```

可选：先用 1 条 Dev 检查连通性，然后继续同一轮：

```powershell
python classifier.py --provider anthropic --model YOUR_MODEL_ID --limit 1
python classifier.py --provider anthropic --model YOUR_MODEL_ID
```

不要根据第一条结果修改 prompt 后继续同一个 run。脚本会核对 prompt、数据、模型、参数，防止混合版本。
脚本默认不显式设置 temperature，使用服务默认值并记录为 null。若模型支持，可通过 --temperature 0 固定，但同一轮不要改变。
对不同 prompt 版本使用不同 --run 名字，例如 --run v1。不在本轮提前创建改进版。

## 输出与队友协作

首次运行创建 runs/baseline_v0/：

- dev_results.csv：81 条原始人工标签、模型预测、理由、TP/FP/FN/TN。
- errors_for_team.csv：误判与未完成项，以及供队友填写的分析列。
- metrics.json：overall、clear、edge 的 precision、recall、F1、accuracy 和覆盖率。
- evaluation.md：confusion matrix 和结果概览。
- run_config.json、prompt_used.txt：实验配置与完整实际 prompt。
- raw_responses.jsonl：每次原始 API 返回，用于复核、usage 记录和断点续跑。不包含请求密钥。

发给队友：dev_results.csv、errors_for_team.csv、evaluation.md、prompt_used.txt、run_config.json。
队友填写误判原因、policy/model 问题和改进建议，之后共同决定 V1。
CSV 可用 Excel 打开；若另存为别的格式，保留原始 CSV 作为本轮记录。

## 评估规则

Positive = Violation。TP 为正确识别违规，FP 为误伤不违规，FN 为漏掉违规，TN 为正确放行。
Precision=TP/(TP+FP)，Recall=TP/(TP+FN)，F1=2TP/(2TP+FP+FN)。分母为零时保存 null，不假装是 0 或 1。
请求失败、无效 JSON、无效标签都保留为 Unscored，不会改成 Non-violation。
有 Unscored 时的指标只反映成功分类的子集，先解决失败项再比较版本。
中断后重复同一命令：成功项跳过，失败项重试。每条返回后保存进度。
整体标签为 36 条 Violation、45 条 Non-violation；17 条是 Edge case。
这轮只能称为 Dev 结果，不是 held-out test 表现。

## 数据来源与边界

dev.csv 从已划分文件的 Dev 工作表提取，ID、原始行号、评论、来源、最终标签及难度原样保留。
模型只收到政策和 review 字段。标注、难度、来源、ID、讨论备注不发送给模型。
没有图像、购买日期或跨账号行为输入；依赖这些证据的政策条目在此文字分类任务中可能无法判定，应在错误分析里讨论。

## API 文档

- https://platform.openai.com/docs/api-reference/chat/create
- https://platform.claude.com/docs/en/api/messages/create

使用兼容服务时也要核对其官方接口文档。API 或模型限制产生的错误需调整配置后重试，不能当作分类结果。
