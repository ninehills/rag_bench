#!/usr/bin/env python3
"""
通用工具函数
"""

import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Union


def load_file(file_path: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    通用文件加载函数，支持 yaml、json、jsonl 格式
    
    Args:
        file_path: 文件路径
        
    Returns:
        加载的数据（列表或字典）
    """
    file_path_obj = Path(file_path)
    
    if file_path_obj.suffix.lower() in ['.yaml', '.yml']:
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    elif file_path_obj.suffix.lower() == '.json':
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif file_path_obj.suffix.lower() == '.jsonl':
        data = []
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line.strip()))
        return data
    else:
        raise ValueError(f"不支持的文件格式: {file_path_obj.suffix}")


def load_questions_as_list(file_path: str) -> List[Dict[str, Any]]:
    """
    加载问题文件，返回列表格式
    
    Args:
        file_path: 问题文件路径
        
    Returns:
        问题数据列表
    """
    return load_file(file_path)


def load_questions_as_dict(file_path: str) -> Dict[str, Dict[str, Any]]:
    """
    加载问题文件，返回以ID为键的字典格式，保持原始顺序
    
    Args:
        file_path: 问题文件路径
        
    Returns:
        以问题ID为键的有序字典
    """
    from collections import OrderedDict
    
    data = load_file(file_path)
    if isinstance(data, list):
        # 使用OrderedDict确保保持原始列表的顺序
        return OrderedDict((item['id'], item) for item in data)
    else:
        # 如果已经是字典格式，直接返回
        return data


def save_json(data: Any, file_path: str, indent: int = 2):
    """
    保存数据到JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 输出文件路径
        indent: JSON缩进
    """
    # 确保输出目录存在
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def setup_llm_cache(cache_file: str = "llm_cache.db"):
    """
    设置LLM缓存
    
    Args:
        cache_file: 缓存文件路径
    """
    from langchain_community.cache import SQLiteCache
    from langchain.globals import set_llm_cache
    
    set_llm_cache(SQLiteCache(database_path=cache_file))