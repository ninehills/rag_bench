# RAG Bench

## Install

```bash
git clone https://github.com/ninehills/rag_bench.git
git submodule update --init --recursive

pip install -r requirements.txt
```

## 招股说明书数据集评测

参见 `rag_bench/data/caibao/README.md`


### Baseline 实现

Baseline 实现在 `baseline` 目录下。

```bash
cd baseline

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
    --doc_dir ../data/caibao/dev_pdf/ \
    --corpus_file output/dev_corpus.json

# 执行索引构建（BM25）
python index.py \
    --corpus_file output/dev_corpus.json \
    --index_file output/dev.index

# 执行批量问答
python qa.py \
    --input_file ../data/caibao/dev.yaml \
    --output_file output/dev_result.json \
    --index_file output/dev.index \
    --batch_size 10

# 执行评测脚本
python evaluation.py \
    --input_file ../data/caibao/dev.yaml \
    --answer_file output/dev_result.json \
    --eval_results_file output/dev_eval_results.json \
    --batch_size 10

# 执行人工复核
python gradio_judge.py  \
    --input_file output/dev_eval_results.json \
    --judge_results_file output/dev_judge_results.json \
    --host 0.0.0.0 \
    --port 7860
```

## GraphGen 生成 QA 问答对

TODO:
1. 关联对应的 page和content
2. 优化提示词，不要抽取非关键因素
3. 支持对结果的二次过滤

在 `gen_qa` 目录下

1. 重命名 `env.template` 为 `.env`，更新其中内容
```ini
# 比较强的模型
SYNTHESIZER_MODEL=
SYNTHESIZER_BASE_URL=
SYNTHESIZER_API_KEY=
# 支持 logits 输出的模型（没有的话会fallback，vLLM部署的服务支持）
TRAINEE_MODEL=
TRAINEE_BASE_URL=
TRAINEE_API_KEY=
```

2. 去baseline 中生成 corpus 文件（见上）

3. 执行生成 QA 问答对
```bash
python generate_qa.py --input_file ../rag_bench/baseline/output/dev_corpus.json --output_file output/dev_qa_gen.json --type atomic --sample 1

# type 可以换 cot/aggregated/multi_hop 
```

注意：
1. 生成 QA 对需要大量 LLM 调用，建议使用本地部署的模型服务，如 vLLM。
2. 生成的 QA对的质量参差不齐，建议人工复核后，使用 Prompt 进行二分类。Prompt 参考

```txt
请判断给定的问题是否满足以下要求：

1. 问题应该有且只有一个明确且无争议的实体作为答案，且问题表述中不应存在任
何形式的模糊性或歧义。例如，避免提问“巴拉克和米歇尔·奥巴马在哪里会面？”因
为无法确定是指哪一次会面；同样不要问“白民国人身体的特点是什么？”因为这
个问题过于模糊，没有明确的答案。注意如果回答是多个实体也不满足要求，例
如：“软体动物、腕足动物及被囊动物”
2. 问题的答案应当是时间不变的，不会随着时间的推移而改变。例如，“美国现任总
统是谁？”就不是一个合适的问题，因为总统身份会随选举结果改变。
3. 问题应该有主体，例如“中国的首都是哪里？”，而不是使用代词，如“我”、“本文”等。

请依据上述标准，审查并确保提出的问题及其答案符合要求，如果不满足上面任一
要求，则输出原因，最后输出“【不合格】”， 否则输出检索材料对应的片段，最后
输出“【合格】”
```