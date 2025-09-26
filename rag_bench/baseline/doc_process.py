#!/usr/bin/env python3
"""
轻量级PDF文档处理脚本，使用PyMuPDF提取文本内容
"""

import argparse
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF
import base62

from langchain_core.documents import Document

def generate_short_id(input_str: str) -> str:
    """
    生成短ID，使用base62编码的SHA256哈希

    Args:
        input_str (str): 输入字符串

    Returns:
        str: 生成的短ID
    """
    # 使用SHA256哈希，
    hash_bytes = hashlib.sha256(input_str.encode('utf-8')).digest()
    # 使用base62编码
    return base62.encodebytes(hash_bytes)


def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    从PDF文件中提取文本内容

    Args:
        pdf_path (str): PDF文件路径

    Returns:
        List[Dict[str, Any]]: 包含每页文本内容的列表
    """
    pages: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text() # type: ignore

            # 清理文本内容
            text = text.strip()
            if text:  # 只添加非空页面
                pages.append({
                    "page_no": page_num + 1,  # 页码从1开始
                    "content": text
                })

        doc.close()

    except Exception as e:
        print(f"处理PDF文件 {pdf_path} 时出错: {e}")

    return pages


def process_documents(doc_dir: str, corpus_file: str) -> None:
    """
    处理目录下的所有PDF文档

    Args:
        doc_dir (str): PDF文档目录
        corpus_file (str): 输出语料库文件路径
    """
    doc_dir_path = Path(doc_dir)
    corpus_file_path = Path(corpus_file)

    # 创建输出目录
    corpus_file_path.parent.mkdir(parents=True, exist_ok=True)

    corpus: List[Document] = []

    # 处理目录下的所有PDF文件
    pdf_files = list(doc_dir_path.glob("*.pdf")) + list(doc_dir_path.glob("*.PDF"))

    if not pdf_files:
        print(f"在目录 {doc_dir_path} 中未找到PDF文件")
        return

    print(f"发现 {len(pdf_files)} 个PDF文件")

    for pdf_file in pdf_files:
        print(f"正在处理: {pdf_file.name}")

        pages = extract_text_from_pdf(str(pdf_file))

        for page in pages:
            corpus_item = Document(
                id=generate_short_id(f"{pdf_file.name}_page_{page['page_no']}_{page['content'][:100]}"),
                metadata=dict(
                    source_file=pdf_file.name,
                    page_no=page["page_no"],
                ),
                page_content=page["content"]
            )
            corpus.append(corpus_item)

    # 保存语料库
    corpus_dicts = [item.model_dump() for item in corpus]
    with open(corpus_file_path, 'w', encoding='utf-8') as f:
        json.dump(corpus_dicts, f, ensure_ascii=False, indent=2)

    print(f"文档处理完成，共处理 {len(corpus)} 个页面")
    print(f"语料库已保存到: {corpus_file_path}")


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='PDF文档处理脚本')
    parser.add_argument('--doc_dir', required=True, help='PDF文档目录')
    parser.add_argument('--corpus_file', required=True, help='输出语料库文件路径')

    args = parser.parse_args()

    process_documents(args.doc_dir, args.corpus_file)


if __name__ == "__main__":
    main()