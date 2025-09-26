#!/usr/bin/env python3
"""
QA问答对生成脚本
使用GraphGen库生成不同类型的问答对

"""

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
import yaml


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="生成QA问答对")
    parser.add_argument(
        "--input_file",
        required=True,
        help="输入的corpus文件路径 (dev_corpus.jsonl)"
    )
    parser.add_argument(
        "--output_file",
        required=True,
        help="输出的QA文件路径 (dev_qa_generated.jsonl)"
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=["aggregated", "atomic", "cot", "multi_hop"],
        help="问题类型"
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="从原始corpus中随机采样的数量，不指定则使用全部数据"
    )
    parser.add_argument(
        "--trainee_model_enable",
        action="store_true",
        help="启用trainee模型进行quiz和judge，默认只使用synthesizer模型"
    )
    return parser.parse_args()


def create_output_dir() -> Path:
    """创建输出目录"""
    output_dir = Path("output/")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def convert_corpus_format(input_file: str, output_file: Path, sample_size: int = None) -> None:
    """将baseline格式的corpus转换为GraphGen期望的格式"""
    # 根据文件扩展名判断输入格式
    input_path = Path(input_file)

    if input_path.suffix == '.jsonl':
        # JSONL格式，逐行读取
        baseline_corpus = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    baseline_corpus.append(json.loads(line))
    else:
        # JSON格式
        with open(input_file, 'r', encoding='utf-8') as f:
            baseline_corpus = json.load(f)

    # 转换格式：从 baseline 格式 {"id": "xxx", "page_content": "xxx", "metadata": {...}}
    # 转换为 GraphGen 格式 {"content": "xxx"}
    graphgen_corpus = []
    for item in baseline_corpus:
        if 'page_content' in item and item['page_content'].strip():
            graphgen_corpus.append({"content": item['page_content']})

    # 如果指定了采样数量，则进行随机采样
    if sample_size is not None and sample_size < len(graphgen_corpus):
        print(f"从 {len(graphgen_corpus)} 条记录中随机采样 {sample_size} 条（随机种子=42）")
        random.seed(42)  # 固定随机种子
        graphgen_corpus = random.sample(graphgen_corpus, sample_size)

    # 写入转换后的文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in graphgen_corpus:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"转换完成: {len(graphgen_corpus)} 条记录写入 {output_file}")


def get_config_file(question_type: str) -> Path:
    """根据问题类型获取配置文件路径"""
    config_file = Path(f"graphgen_config_tpl/{question_type}_config.yaml")

    if not config_file.exists():
        print(f"错误: 配置文件不存在: {config_file}")
        sys.exit(1)

    return config_file


def modify_config_for_trainee_model(config_file: Path, trainee_model_enable: bool) -> Path:
    """根据trainee_model_enable参数修改配置文件"""
    # 读取原始配置
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 修改配置以设置trainee模型开关
    if 'quiz_and_judge_strategy' in config:
        config['quiz_and_judge_strategy']['enabled'] = trainee_model_enable

    # 创建临时配置文件，保存到output目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    temp_config = output_dir / f"temp_{config_file.name}"
    with open(temp_config, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    status = "启用" if trainee_model_enable else "禁用"
    print(f"已创建临时配置文件（{status}trainee模型）: {temp_config}")
    return temp_config


def run_graphgen(config_file: Path, output_dir: Path, trainee_model_enable: bool = False) -> None:
    """执行GraphGen生成命令"""
    # 修改配置文件以设置trainee模型开关
    actual_config_file = modify_config_for_trainee_model(config_file, trainee_model_enable)

    cmd = [
        sys.executable, "-m", "graphgen.generate",
        "--config_file", str(actual_config_file),
        "--output_dir", str(output_dir)
    ]

    print(f"执行命令: {' '.join(cmd)}")
    print(f"工作目录: {os.getcwd()}")
    if trainee_model_enable:
        print("注意: 已启用trainee模型")
    else:
        print("注意: 使用默认配置（禁用trainee模型）")

    try:
        # 在当前目录执行命令，传递当前进程的环境变量给子进程，实时输出
        env = os.environ.copy()

        # 直接将子进程的stdout和stderr重定向到当前进程，实现实时输出
        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            env=env,
            stdout=None,  # 直接输出到终端
            stderr=None   # 直接输出到终端
        )

        # 检查返回码
        if result.returncode == 0:
            print("GraphGen执行成功!")
        else:
            print(f"GraphGen执行失败，返回码: {result.returncode}")
            sys.exit(1)

    except Exception as e:
        print(f"GraphGen执行失败: {e}")
        sys.exit(1)

    finally:
        # 清理临时配置文件
        try:
            actual_config_file.unlink()
            print(f"已清理临时配置文件: {actual_config_file}")
        except Exception as e:
            print(f"清理临时配置文件失败: {e}")


def copy_results(output_dir: Path, final_output_file: str, question_type: str) -> None:
    """将生成的结果复制到最终输出位置并转换为标准格式"""
    # GraphGen会在output_dir/data/graphgen/{unique_id}/下生成结果文件
    # 查找qa-*.json文件
    qa_files = list(output_dir.glob("data/graphgen/*/qa-*.json"))

    if not qa_files:
        # 如果没有找到，尝试查找其他JSON文件
        qa_files = list(output_dir.glob("**/*.json"))
        qa_files = [f for f in qa_files if f.name.startswith('qa-')]

    if not qa_files:
        print(f"警告: 在 {output_dir} 中未找到生成的qa文件")
        return

    # 假设取第一个生成的qa文件
    source_file = qa_files[0]
    print(f"找到生成的文件: {source_file}")

    # 读取GraphGen生成的结果
    with open(source_file, 'r', encoding='utf-8') as f:
        qa_data = json.load(f)

    # 转换为标准格式（类似dev.yaml的JSON格式）
    formatted_qa = []
    for i, qa_item in enumerate(qa_data):
        # GraphGen的格式是 {"messages": [{"role": "user", "content": "问题"}, {"role": "assistant", "content": "答案"}]}
        messages = qa_item.get("messages", [])
        user_message = None
        assistant_message = None

        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
            elif msg.get("role") == "assistant":
                assistant_message = msg.get("content", "")

        formatted_item = {
            "id": f"{question_type}-{i}",
            "metadata": {
                "category": question_type,
                "modal": "文本",
                "turn": "单轮"
            },
            "query": user_message or "",
            "history": [],
            "golden_answer": assistant_message or "",
            "related_documents": []  # GraphGen生成的问答对通常不包含具体文档引用
        }
        formatted_qa.append(formatted_item)

    # 确保输出目录存在
    output_path = Path(final_output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入JSON格式（而不是JSONL）
    with open(final_output_file, 'w', encoding='utf-8') as f:
        json.dump(formatted_qa, f, ensure_ascii=False, indent=2)

    print(f"结果已转换并保存到: {final_output_file} (共 {len(formatted_qa)} 条记录)")


def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()
    print(f"加载环境变量文件: {os.path.join(os.getcwd(), '.env')}")

    args = parse_args()

    # 检查输入文件是否存在
    if not Path(args.input_file).exists():
        print(f"错误: 输入文件不存在: {args.input_file}")
        sys.exit(1)

    print(f"开始生成 {args.type} 类型的QA问答对...")

    # 1. 创建输出目录
    output_dir = create_output_dir()
    print(f"创建输出目录: {output_dir}")

    # 2. 转换corpus格式
    corpus_file = output_dir / "corpus.jsonl"
    convert_corpus_format(args.input_file, corpus_file, args.sample)

    # 3. 获取配置文件
    config_file = get_config_file(args.type)
    print(f"使用配置文件: {config_file}")

    # 4. 执行GraphGen
    run_graphgen(config_file, output_dir, args.trainee_model_enable)

    # 5. 复制结果到最终位置
    copy_results(output_dir, args.output_file, args.type)

    print(f"QA生成完成! 结果保存在: {args.output_file}")


if __name__ == "__main__":
    main()