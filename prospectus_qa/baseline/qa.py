#!/usr/bin/env python3
"""
批量问答工具
基于 app.py 中的 RAG 实现，支持批量处理问答任务
"""

import os
import json
import argparse
import yaml
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from langchain_community.retrievers import BM25Retriever
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_fixed

from index import load_index, chinese_tokenize # noqa: F401
from utils import load_questions_as_list, save_json, setup_llm_cache

from dotenv import load_dotenv

load_dotenv()
# Langchain OpenAI 的BASE_URL配置和 openai sdk 的配置不同
os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_BASE_URL", "")

# 设置SQLite缓存
setup_llm_cache()


# 使用utils中的函数，保持向后兼容
def load_input_file(file_path: str) -> List[Dict[str, Any]]:
    """加载输入文件（向后兼容函数）"""
    return load_questions_as_list(file_path)


def setup_llm():
    """设置语言模型"""
    return ChatOpenAI(model=os.environ.get('ANSWER_MODEL', 'Qwen/Qwen3-14B'), temperature=0.5)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def ask(llm: ChatOpenAI, query: str, retrieved_docs):
    """
    基于检索结果回答问题

    Args:
        llm: 语言模型
        query: 问题
        retrieved_docs: 检索到的文档

    Returns:
        回答结果
    """
    ctx = "\\n---\\n".join([doc.page_content for doc in retrieved_docs])
    prompt = (
        "根据参考资料回答问题。\\n\\n"
        f"问题：{query}\\n\\n参考资料：\\n{ctx}\\n\\n请回答：{query}"
    )

    try:
        result = llm.invoke([{"role": "user", "content": prompt}])
        return result.content  # 提取AIMessage的文本内容
    except Exception as e:
        print(f"回答问题时出错: {e}")
        return "抱歉，无法回答此问题。"


def process_question(item: Dict[str, Any], bm25_retriever: BM25Retriever, llm: ChatOpenAI) -> Dict[str, Any]:
    """
    处理单个问题

    Args:
        item: 问题数据
        bm25_retriever: BM25 检索器
        llm: 语言模型

    Returns:
        处理结果
    """
    query = item["query"]
    question_id = item["id"]

    # BM25 检索
    bm25_retriever.k = 3  # 设置检索数量
    retrieved_docs = bm25_retriever.invoke(query)

    print(f"问题 ID: {question_id}, 检索到 {len(retrieved_docs)} 个文档")

    # 生成答案
    answer = ask(llm, query, retrieved_docs)

    # 构建结果
    result = {
        "id": question_id,
        "query": query,
        "answer": answer,
        "documents": [
            {
                "source_file": doc.metadata.get("source_file", ""),
                "page_no": doc.metadata.get("page_no", 0),
                "content": doc.page_content,
                "score": 0  # BM25 目前的检索器实现没有返回分数
            }
            for doc in retrieved_docs
        ]
    }

    return result


def batch_process(questions: List[Dict[str, Any]], bm25_retriever, llm, batch_size: int = 3):
    """
    批量处理问题，保持原始顺序

    Args:
        questions: 问题列表
        bm25_retriever: BM25 检索器
        llm: 语言模型
        batch_size: 批处理大小

    Returns:
        处理结果列表（与输入顺序一致）
    """
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        # 提交任务，保持与原始问题的对应关系
        futures = [
            executor.submit(process_question, item, bm25_retriever, llm)
            for item in questions
        ]

        # 按原始顺序获取结果
        results = []
        for i, future in enumerate(tqdm(futures, desc="处理问题")):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                question = questions[i]
                print(f"处理问题 {question['id']} 时出错: {e}")
                # 添加错误结果
                results.append({
                    "id": question["id"],
                    "query": question["query"],
                    "answer": "处理失败",
                    "documents": []
                })

    return results


def save_results(results: List[Dict[str, Any]], output_file: str):
    """
    保存结果到文件

    Args:
        results: 结果列表
        output_file: 输出文件路径
    """
    save_json(results, output_file)
    print(f"结果已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='批量问答工具')
    parser.add_argument('--input_file', required=True, help='输入文件路径 (支持 yaml/json/jsonl)')
    parser.add_argument('--output_file', required=True, help='输出文件路径')
    parser.add_argument('--index_file', default='output/dev.index', help='BM25 索引文件路径，默认为 output/dev.index')
    parser.add_argument('--batch_size', type=int, default=3, help='批处理大小')
    parser.add_argument('--sample', help='只处理指定 ID 的问题')

    args = parser.parse_args()

    # 检查输入文件
    if not Path(args.input_file).exists():
        print(f"错误: 输入文件不存在: {args.input_file}")
        return

    # 加载输入数据
    print(f"加载输入文件: {args.input_file}")
    questions = load_input_file(args.input_file)
    print(f"加载问题数量: {len(questions)}")

    # 过滤特定问题
    if args.sample:
        questions = [q for q in questions if q["id"] == args.sample]
        if not questions:
            print(f"错误: 未找到 ID 为 {args.sample} 的问题")
            return
        print(f"只处理问题: {args.sample}")

    # 设置检索器和模型
    print("设置 BM25 检索器...")
    bm25_retriever  = load_index(args.index_file)

    print("设置语言模型...")
    llm = setup_llm()

    # 批量处理
    print("开始批量处理...")
    results = batch_process(questions, bm25_retriever, llm, args.batch_size)

    # 保存结果
    save_results(results, args.output_file)

    print(f"处理完成，共处理 {len(results)} 个问题")


if __name__ == "__main__":
    main()