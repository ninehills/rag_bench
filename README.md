# RAG Bench

## Install

```bash
git clone https://github.com/ninehills/rag_bench.git
git submodule update --init --recursive
```

## 招股说明书数据集评测

参见 `rag_bench/data/caibao/README.md`


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

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```
