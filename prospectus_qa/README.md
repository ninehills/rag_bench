# 招股说明书知识问答数据集

## 数据来源

数据来自[博金大模型挑战赛-金融千问14b数据集](https://www.modelscope.cn/datasets/BJQW14B/bs_challenge_financial_14b_dataset/summary)中的招股说明书 80 份 PDF 文件，并没有使用其 Questions 数据（质量较低）。

本项目将 80 份 PDF 文件重命名为 `<公司名称>.pdf`，并分别放入 `data/dev_pdf` 和 `data/val_pdf` 目录下。

这些招股说明书文件多数并不是扫描件，但具备复杂的表格、流程图等元素。

## 数据集格式

评测数据集使用 JSON/YAML 格式（自动识别），格式如下：

```json
[{
    "id": "test-0", # 数据唯一标识
    "metadata": { # 可以根据需求增加更多的 Key-Value 标签，比如问题维度等
        "difficulty": "简单", # 问题难度，简单、中等、困难
        "category": "多跳推理", # 问题分类
        "modal": "文本", # 模态，包括文本、表格、图片
        "turn": "单轮", # 问题轮次，比如 单轮、多轮等，单轮问题应该占多数。
    },
    "query": "用户问题", # 用户的原始提问
    "history": [{"role": "user", "content": "用户问题"}, {"role": "assistant", "content": "模型回复"}], # 多轮对话历史会话，单轮对话为空数组。
    "golden_answer": "人工标注的黄金答复", # 人工标注的黄金答复，可以由大模型生成后人工修订而来
    "related_documents": [ # 可以包含多个内容
        {"source_file": "xxxx", "page_no": 12, "content": "文档中的相关段落内容"} # source_file：原始文档名称，page_no：文档中的页码，content: 文档中的相关段落内容，如果是表格使用 <table></table> HTML 格式
    ]
}]
```

问题分类如下（参考 [CRAG](https://arxiv.org/abs/2406.04744) 定义）：

| 问题类型 | 定义 |
|---------|------|
| 事实 | 询问不太可能随时间变化的简单事实，例如一个人的出生日期和一本书的作者。 |
| 条件 | 询问带有特定条件的简单事实，例如某个日期的股票价格和某个导演在特定类型的最新电影。 |
| 集合 | 期望得到一组实体或对象作为答案的问题（例如，"南半球有哪些大洲？"）。 |
| 比较 | 比较两个实体的问题（例如，"谁更早开始表演，Adele还是Ed Sheeran？"）。 |
| 聚合 | 需要对检索结果进行聚合才能回答的问题（例如，"Meryl Streep赢得了多少个奥斯卡奖？"）。 |
| 多跳 | 需要串联多个信息片段才能组成答案的问题（例如，"谁在李安最新的电影中出演女主角？"）。 |
| 后处理 | 需要对检索到的信息进行推理或处理才能获得答案的问题（例如，"Thurgood Marshall担任最高法院法官多少天？"）。 |
| 错误前提 | 具有错误预设或假设的问题（例如，"Taylor Swift在转型流行音乐之前的说唱专辑叫什么名字？"（Taylor Swift从未发行过说唱专辑））。 |

注意：请不要根据 metadata 进行区别处理，实际给到评测的 val.json 格式如下：

```json
[{
    "id": "test-0", # 数据唯一标识
    "query": "用户问题", # 用户的原始提问
    "history": [{"role": "user", "content": "用户问题"}, {"role": "assistant", "content": "模型回复"}], # 多轮对话历史会话，单轮对话为空数组。
}]
```

## 数据集分布

| 文件名 | 数据集类型 | 条数 | 说明 |
| --- | --- | --- | --- |
| `data/dev.json` | dev | 10 | 覆盖全部问题类型和问题轮次，单轮问题占多数 |
| `data/val.json`, `data/val_input.json` | val | 100 | 按照实际业务中的比例构造 |

`val_input.json` 是实际给到业务系统评测的验证集输入，仅包括 id、query 和 history 字段。

## 评测指标

### 问答指标

使用 CRAG 的评测方式，评估时先构造 LLM Prompt 进行初步评估，然后人工复核。

- 完美（1分）。回答正确地解答了用户的问题，且不包含任何虚构的内容。
- 可接受（0.5分）。回答为用户的问题提供了有用的答案，但可能包含不影响答案实用性的小错误。
- 缺失（0分）。回答是"我不知道"、"抱歉我找不到..."、系统错误（如空白回答），或系统要求澄清原始问题。
- 错误（-1分）。回答提供了错误或无关的信息来回答用户的问题（惩罚模型幻觉以适配实际场景）。

### 检索指标

检索是开发指标，并不是端到端的指标，分为：

- PageRecall@N：检索到的页面的 TopN 召回率。
- PageMRR@N：检索到的页面的 TopN 平均检索排名（MRR）。
- ContentRecall@N：检索到的段落的 TopN 召回率。
- ContentMRR@N：检索到的段落的 TopN 平均检索排名（MRR）。

N 取值： 1、3、5、10（只评估 Top10，不关注检索系统的切片情况）

### 提交文件格式

示例提交文件为 `data/result.json`，格式如下

```json
[{
    "id": "dev-0", # 数据唯一标识，和 dev/val 数据集的 id 保持一致
    "answer": "模型回复", # 模型的回答
    "documents": [ # 按照分数倒序排序，分数必须归一化到0-1 中间，其他调试用字段需要用下划线开头会直接忽略。
        {"source_file": "xxxx", "page_no": 12, "content": "文档中的相关段落内容", "score": 0.91} # source_file：原始文档名称，page_no：文档中的页码，content: 文档中的相关段落内容，如果是表格使用 <table></table> HTML 格式
    ]
}]
```

注意：切分的时候强制不跨页，避免跨页无法评估。

### Baseline 实现

Baseline 实现在 `baseline` 目录下。

```bash
cd baseline
pip install -r requirements.txt

cp env.template .env
# 配置 .env 中的模型调用参数
ANSWER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.xx.cn/v1

JUDGE_MODEL=openai/gpt-4o-mini
### 不配置的话复用 OPENAI_API_KEY/OPENAI_BASE_URL
# JUDGE_OPENAI_API_KEY=xxx
# JUDGE_OPENAI_BASE_URL=https://api.xx.cn/v1

# 执行文档处理
python doc_process.py \
    --doc_dir ../data/dev_pdf/ \
    --corpus_file output/dev_corpus.json

# 执行索引构建（BM25）
python index.py \
    --corpus_file output/dev_corpus.json \
    --index_file output/dev.index

# 执行批量问答
python qa.py \
    --input_file ../data/dev.yaml \
    --output_file output/dev_result.json \
    --index_file output/dev.index \
    --batch_size 10

# 执行评测脚本
python evaluation.py \
    --input_file ../data/dev.yaml \
    --answer_file output/dev_result.json \
    --eval_results_file output/dev_eval_results.json \
    --batch_size 10

# 执行人工复核
python manual_judge.py \
    --input_file output/dev_eval_results.json \
    --judge_results_file output/dev_judge_results.json
```
