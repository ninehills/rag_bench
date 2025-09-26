#!/usr/bin/env python3
"""
BM25 索引构建工具
基于 app.py 中的 BM25 实现，用于构建和保存 BM25 索引
"""

import json
import pickle
import argparse
from pathlib import Path
from typing import List

import jieba
from langchain_community.retrievers import BM25Retriever
from langchain.schema import Document


def load_corpus(corpus_file: str) -> List[Document]:
    """
    从语料库文件加载文档

    Args:
        corpus_file: 语料库文件路径

    Returns:
        Document 对象列表
    """
    with open(corpus_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    for item in data:
        doc = Document(**item)
        documents.append(doc)

    return documents


def chinese_tokenize(text: str) -> List[str]:
    """
    使用 jieba 对中文文本进行分词

    Args:
        text: 输入文本

    Returns:
        分词后的词语列表
    """
    return list(jieba.cut(text))

def build_bm25_index(documents: List[Document]) -> BM25Retriever:
    """
    构建 BM25 索引

    Args:
        documents: 文档列表

    Returns:
        BM25Retriever 对象
    """
    print(f"正在构建 BM25 索引，文档数量: {len(documents)}")

    # 使用 langchain 的 BM25Retriever，设置中文分词器
    bm25_retriever = BM25Retriever.from_documents(
        documents=documents,
        preprocess_func=chinese_tokenize
    )

    print("BM25 索引构建完成")
    return bm25_retriever


def save_index(bm25_retriever: BM25Retriever, output_path: str):
    """
    保存 BM25 索引到文件

    Args:
        bm25_retriever: BM25 检索器
        output_path: 输出文件路径
    """
    print(f"正在保存索引到: {output_path}")

    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 保存索引
    with open(output_path, 'wb') as f:
        pickle.dump(bm25_retriever, f)

    print("索引保存完成")

def load_index(index_file: str) -> BM25Retriever:
    """
    加载 BM25 索引

    Args:
        index_file: 索引文件路径

    Returns:
        BM25Retriever 对象
    """
    with open(index_file, 'rb') as f:
        return pickle.load(f)

def main():
    parser = argparse.ArgumentParser(description='构建 BM25 索引')
    parser.add_argument('--corpus_file', required=True, help='语料库文件路径')
    parser.add_argument('--index_file', required=True, help='索引文件名')

    args = parser.parse_args()

    # 检查输入文件是否存在
    if not Path(args.corpus_file).exists():
        print(f"错误: 语料库文件不存在: {args.corpus_file}")
        return

    # 加载语料库
    print(f"正在加载语料库: {args.corpus_file}")
    documents = load_corpus(args.corpus_file)
    print(f"加载文档数量: {len(documents)}")

    # 构建索引
    bm25_retriever = build_bm25_index(documents)

    # 保存索引
    save_index(bm25_retriever, args.index_file)

    print(f"索引构建完成，保存在: {args.index_file}")


if __name__ == "__main__":
    main()