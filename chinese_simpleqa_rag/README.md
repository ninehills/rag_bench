# Chinese SimpleQA 知识问答数据集

> 设计后发现检索难度还是太低，重点还是只能考察生成。而且和实际的场景关系不大，放弃。

## 数据来源

数据来自[Chinese SimpleQA](https://openstellarteam.github.io/ChineseSimpleQA/)中的 3000 条数据。

数据中的 corpus 是链接，我们已经将所有的 URL 下载并提取正文，同时增加了部分干扰数据。

干扰数据：
- 使用维基百科简体中文快照，然后用BM25索引后，使用query检索
- 根据页面的ROUGE-L和URL过滤掉已经确定的URL及内容（用ROUGE-L可以兼容百度百科）
- 取Top3-Top10（不取Top3是担心上一部的去重没有去好）

## 数据集格式

评测数据集使用 JSONL 格式，每行如下：

```json
{
    "id": "97e7f58a3b154facaa3a5c64d678c7bf", # 数据唯一标识
    "metadata": { # 使用SimpleQA 中的metadata
        "primary_category": "",
        "secondary_category": "",
        "urls": []
    },
    "query": "用户问题", # 用户的原始提问
    "golden_answer": "人工标注的黄金答复", # 人工标注的黄金答复，可以由大模型生成后人工修订而来
    "related_documents": [ # 可以包含多个内容
        {"corpus_id": "corpus-0"} # 对应的corpus_id
    ]
}
```

## 数据集分布

| 文件名 | 数据集类型 | 条数 | 说明 |
| --- | --- | --- | --- |
| `data/corpus.jsonl` | corpus | N | 全量文档，格式为 `{"id": "xxx", "url": "xxx", "content": "xxx"}` | 
| `data/dev_corpus.jsonl` | corpus | 100 | 为 dev 准备少量文档，用于调试| 
| `data/dev.jsonl` | dev | 10 | 固定种子随机拆分 |
| `data/val.jsonl`, `data/val_input.jsonl` | val | 100 | 固定种子随机拆分 |
| `data/test.jsonl`, `data/test_input.jsonl` | test | 3000 | 全量数据 |

`<val/test>_input.jsonl` 是实际给到业务系统评测的验证集输入，仅包括 id、query 字段。

## 评测指标

### 问答指标

使用 [Chinese SimpleQA 相同的评测方法](https://github.com/OpenStellarTeam/ChineseSimpleQA/blob/master/chinese_simpleqa_eval.py)。

指标为：

- Accuracy
- F1

### 检索指标

检索是开发指标，并不是端到端的指标，分为：

- Recall@N：检索 TopN 召回率。
- MRR@N：检索 TopN 平均检索排名（MRR）。

N 取值： 1、3、5、10

### 提交文件格式

示例提交文件为 `data/result.jsonl`，每行格式如下

```json
{
    "id": "dev-0", # 数据唯一标识
    "answer": "模型回复", # 模型的回答
    "documents": [ # 按照分数倒序排序，分数必须归一化到0-1 中间，其他调试用字段需要用下划线开头会直接忽略。
        ["corpus_id": "xxx", "score": 0.91] 
    ]
}
```

注意：切分的时候强制不跨页，避免跨页无法评估。

### Baseline 实现

Baseline 实现在 `baseline` 目录下。

```bash
cd baseline
pip install -r requirements.txt

# 配置 .env 中的模型调用参数
ANSWER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.xx.cn/v1

JUDGE_MODEL=openai/gpt-4o-mini
### 不配置的话复用 OPENAI_API_KEY/OPENAI_BASE_URL
# JUDGE_OPENAI_API_KEY=xxx
# JUDGE_OPENAI_BASE_URL=https://api.xx.cn/v1


# 执行索引构建（BM25）
python index.py \
    --corpus_file dev_corpus.jsonl

# 执行批量问答
python qa.py \
    --input_file ../data/dev.jsonl \
    --output_file dev_result.jsonl \
    --batch_size 3

# 执行评测脚本
python eval.py \
    --input_file ../data/dev.jsonl \
    --answer_file dev_result.jsonl
    --eval_results_file dev_eval_results.json
```


