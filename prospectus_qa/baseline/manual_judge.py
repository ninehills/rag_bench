#!/usr/bin/env python3
"""
人工评估工具
用于对自动评估结果进行人工复核和修改
"""

import os
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from utils import load_file, save_json


@dataclass
class JudgeSession:
    """人工评估会话数据"""
    input_file: str
    output_file: str
    current_index: int = 0
    total_count: int = 0
    judged_count: int = 0
    start_time: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_file': self.input_file,
            'output_file': self.output_file,
            'current_index': self.current_index,
            'total_count': self.total_count,
            'judged_count': self.judged_count,
            'start_time': self.start_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JudgeSession':
        return cls(**data)


class ManualJudge:
    """人工评估工具"""
    
    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        self.session_file = output_file.replace('.json', '_session.json')
        
        # 加载数据
        self.data = self._load_input_data()
        self.results = self._load_or_init_results()
        self.session = self._load_or_init_session()
        
    def _load_input_data(self) -> Dict[str, Any]:
        """加载输入数据"""
        if not Path(self.input_file).exists():
            raise FileNotFoundError(f"输入文件不存在: {self.input_file}")
        
        data = load_file(self.input_file)
        if not isinstance(data, dict) or 'detailed_results' not in data:
            raise ValueError("输入文件格式错误，需要包含 detailed_results 字段")
        
        return data
    
    def _load_or_init_results(self) -> Dict[str, Any]:
        """加载或初始化结果数据"""
        if Path(self.output_file).exists():
            return load_file(self.output_file)
        else:
            # 初始化结果数据，复制原始数据结构
            results = self.data.copy()
            # 为每个详细结果添加人工评估字段
            for item in results['detailed_results']:
                item['manual_judgment'] = {
                    'correctness': None,
                    'completeness': None, 
                    'faithfulness': None,
                    'judge_time': None,
                    'notes': ""
                }
            return results
    
    def _load_or_init_session(self) -> JudgeSession:
        """加载或初始化会话数据"""
        if Path(self.session_file).exists():
            session_data = load_file(self.session_file)
            return JudgeSession.from_dict(session_data)
        else:
            return JudgeSession(
                input_file=self.input_file,
                output_file=self.output_file,
                current_index=0,
                total_count=len(self.data['detailed_results']),
                judged_count=0,
                start_time=datetime.now().isoformat()
            )
    
    def _save_session(self):
        """保存会话数据"""
        save_json(self.session.to_dict(), self.session_file)
    
    def _save_results(self):
        """保存结果数据"""
        save_json(self.results, self.output_file)
        print(f"结果已保存到: {self.output_file}")
    
    def _print_header(self):
        """打印头部信息"""
        os.system('clear' if os.name == 'posix' else 'cls')
        print("=" * 80)
        print("RAG 评估结果人工复核工具")
        print("=" * 80)
        print(f"输入文件: {self.input_file}")
        print(f"输出文件: {self.output_file}")
        print(f"进度: {self.session.current_index + 1}/{self.session.total_count} "
              f"(已复核: {self.session.judged_count})")
        print("=" * 80)
    
    def _display_sample(self, sample: Dict[str, Any]):
        """显示样本信息"""
        print(f"\n【样本ID】: {sample['id']}")
        print(f"【问题】: {sample['query']}")
        print(f"\n【AI回答】:")
        print(f"{sample['answer']}")
        print(f"\n【标准答案】:")
        print(f"{sample['golden_answer']}")
        
        # 显示自动评估结果
        gen_metrics = sample.get('generation_metrics', {})
        print(f"\n【自动评估结果】:")
        print(f"正确性: {'✓' if gen_metrics.get('correctness', False) else '✗'}")
        print(f"完整性: {'✓' if gen_metrics.get('completeness', False) else '✗'}")
        print(f"忠诚度: {'✓' if gen_metrics.get('faithfulness', False) else '✗'}")
        
        # 显示已有的人工评估（如果存在）
        manual = sample.get('manual_judgment', {})
        if any(v is not None for v in [manual.get('correctness'), manual.get('completeness'), manual.get('faithfulness')]):
            print(f"\n【当前人工评估】:")
            if manual.get('correctness') is not None:
                print(f"正确性: {'✓' if manual['correctness'] else '✗'}")
            if manual.get('completeness') is not None:
                print(f"完整性: {'✓' if manual['completeness'] else '✗'}")
            if manual.get('faithfulness') is not None:
                print(f"忠诚度: {'✓' if manual['faithfulness'] else '✗'}")
            if manual.get('notes'):
                print(f"备注: {manual['notes']}")
    
    def _get_boolean_input(self, prompt: str, current_value: Optional[bool] = None) -> Optional[bool]:
        """获取布尔值输入"""
        if current_value is not None:
            default_text = f" [当前: {'是' if current_value else '否'}]"
        else:
            default_text = ""
        
        while True:
            choice = input(f"{prompt}{default_text} (是/y/否/n/跳过/s): ").strip().lower()
            if choice in ['是', 'y', 'yes']:
                return True
            elif choice in ['否', 'n', 'no']:
                return False
            elif choice in ['跳过', 's', 'skip', '']:
                return current_value
            else:
                print("无效输入，请输入: 是/y/否/n/跳过/s")
    
    def _judge_sample(self, index: int) -> bool:
        """评估单个样本，返回是否进行了修改"""
        sample = self.results['detailed_results'][index]
        manual = sample['manual_judgment']
        
        self._print_header()
        self._display_sample(sample)
        
        print(f"\n{'='*60}")
        print("请进行人工评估:")
        print("  a/同意 - 同意自动评估结果")
        print("  e/评估 - 手动评估各维度")
        print("  n/下一个, p/上一个, q/退出")
        
        # 获取操作选择
        action = input("\n操作 (同意/a, 评估/e, 下一个/n, 上一个/p, 退出/q): ").strip().lower()
        
        if action in ['q', 'quit', '退出']:
            return False
        elif action in ['p', 'prev', '上一个']:
            if index > 0:
                self.session.current_index = index - 1
            return True
        elif action in ['n', 'next', '下一个', '']:
            if index < self.session.total_count - 1:
                self.session.current_index = index + 1
            else:
                # 已经是最后一个，提示完成
                print("\n已到达最后一个样本！")
                input("按回车退出...")
                return False
            return True
        elif action in ['a', 'agree', '同意']:
            # 同意自动评估结果
            gen_metrics = sample.get('generation_metrics', {})
            manual['correctness'] = gen_metrics.get('correctness', False)
            manual['completeness'] = gen_metrics.get('completeness', False)
            manual['faithfulness'] = gen_metrics.get('faithfulness', False)
            manual['judge_time'] = datetime.now().isoformat()
            manual['notes'] = "同意自动评估"
            
            # 检查是否是新完成的评估
            if manual.get('correctness') is not None and index == self.session.current_index:
                original_manual = self.data['detailed_results'][index].get('manual_judgment', {})
                if not all(v is not None for v in [original_manual.get('correctness'), original_manual.get('completeness'), original_manual.get('faithfulness')]):
                    self.session.judged_count += 1
            
            print("\n已同意自动评估结果！")
            
            # 自动跳转到下一个
            if index < self.session.total_count - 1:
                self.session.current_index = index + 1
                input("按回车继续...")
                return True
            else:
                # 已经是最后一个，提示完成
                print("这是最后一个样本，评估完成！")
                input("按回车退出...")
                return False
        elif action in ['e', 'eval', '评估']:
            # 进行评估
            modified = False
            
            print(f"\n{'='*40}")
            print("评估维度:")
            
            # 正确性评估
            new_correctness = self._get_boolean_input(
                "1. 正确性 (AI回答在事实上是否与标准答案一致)", 
                manual.get('correctness')
            )
            if new_correctness != manual.get('correctness'):
                manual['correctness'] = new_correctness
                modified = True
            
            # 完整性评估
            new_completeness = self._get_boolean_input(
                "2. 完整性 (AI回答是否包含标准答案的所有主要信息点)", 
                manual.get('completeness')
            )
            if new_completeness != manual.get('completeness'):
                manual['completeness'] = new_completeness
                modified = True
            
            # 忠诚度评估
            new_faithfulness = self._get_boolean_input(
                "3. 忠诚度 (AI回答是否存在幻觉)", 
                manual.get('faithfulness')
            )
            if new_faithfulness != manual.get('faithfulness'):
                manual['faithfulness'] = new_faithfulness
                modified = True
            
            # 备注
            current_notes = manual.get('notes', '')
            print(f"\n4. 备注 (可选，当前: {current_notes})")
            new_notes = input("   新备注 (直接回车保持不变): ").strip()
            if new_notes and new_notes != current_notes:
                manual['notes'] = new_notes
                modified = True
            
            if modified:
                manual['judge_time'] = datetime.now().isoformat()
                if all(v is not None for v in [manual.get('correctness'), manual.get('completeness'), manual.get('faithfulness')]):
                    if manual.get('correctness') is not None and index == self.session.current_index:
                        # 检查是否是新完成的评估
                        original_manual = self.data['detailed_results'][index].get('manual_judgment', {})
                        if not all(v is not None for v in [original_manual.get('correctness'), original_manual.get('completeness'), original_manual.get('faithfulness')]):
                            self.session.judged_count += 1
                
                print("\n评估已保存！")
                
                # 自动跳转到下一个
                if index < self.session.total_count - 1:
                    self.session.current_index = index + 1
                    input("\n按回车继续...")
                    return True
                else:
                    # 已经是最后一个，提示完成
                    print("这是最后一个样本，评估完成！")
                    input("按回车退出...")
                    return False
            else:
                print("\n未进行任何修改。")
                input("\n按回车继续...")
                return True
        else:
            print("无效操作")
            input("按回车继续...")
            return True
    
    def _print_final_statistics(self):
        """显示最终统计信息"""
        print(f"\n{'='*80}")
        print("评估完成统计")
        print(f"{'='*80}")
        
        # 基本统计
        print(f"总样本数: {self.session.total_count}")
        print(f"已完成评估: {self.session.judged_count}")
        print(f"完成率: {self.session.judged_count/self.session.total_count*100:.1f}%")
        
        # 计算修正后的指标
        corrected_correctness = 0
        corrected_completeness = 0
        corrected_faithfulness = 0
        manual_judged_count = 0
        
        for sample in self.results['detailed_results']:
            manual = sample.get('manual_judgment', {})
            if all(v is not None for v in [manual.get('correctness'), manual.get('completeness'), manual.get('faithfulness')]):
                manual_judged_count += 1
                if manual['correctness']:
                    corrected_correctness += 1
                if manual['completeness']:
                    corrected_completeness += 1
                if manual['faithfulness']:
                    corrected_faithfulness += 1
        
        if manual_judged_count > 0:
            print(f"\n修正后的指标 (基于 {manual_judged_count} 个已评估样本):")
            print(f"正确性: {corrected_correctness/manual_judged_count:.4f} ({corrected_correctness}/{manual_judged_count})")
            print(f"完整性: {corrected_completeness/manual_judged_count:.4f} ({corrected_completeness}/{manual_judged_count})")
            print(f"忠诚度: {corrected_faithfulness/manual_judged_count:.4f} ({corrected_faithfulness}/{manual_judged_count})")
        
        # 与自动评估结果对比
        auto_metrics = self.data.get('generation_metrics', {})
        if auto_metrics and manual_judged_count > 0:
            print(f"\n自动评估 vs 人工修正对比:")
            print(f"{'指标':<10} {'自动评估':<10} {'人工修正':<10} {'变化':<10}")
            print("-" * 50)
            
            auto_correctness = auto_metrics.get('correctness', 0)
            auto_completeness = auto_metrics.get('completeness', 0) 
            auto_faithfulness = auto_metrics.get('faithfulness', 0)
            
            manual_correctness = corrected_correctness/manual_judged_count
            manual_completeness = corrected_completeness/manual_judged_count
            manual_faithfulness = corrected_faithfulness/manual_judged_count
            
            print(f"{'正确性':<10} {auto_correctness:<10.4f} {manual_correctness:<10.4f} {manual_correctness-auto_correctness:+.4f}")
            print(f"{'完整性':<10} {auto_completeness:<10.4f} {manual_completeness:<10.4f} {manual_completeness-auto_completeness:+.4f}")
            print(f"{'忠诚度':<10} {auto_faithfulness:<10.4f} {manual_faithfulness:<10.4f} {manual_faithfulness-auto_faithfulness:+.4f}")
        
        print(f"\n文件信息:")
        print(f"结果文件: {self.output_file}")
        print(f"会话文件: {self.session_file}")
        print(f"{'='*80}")
    
    def run(self):
        """运行人工评估"""
        print("开始人工评估...")
        
        try:
            while True:
                current_index = self.session.current_index
                
                if current_index >= self.session.total_count:
                    print("\n所有样本已评估完成！")
                    break
                
                if not self._judge_sample(current_index):
                    # 用户选择退出
                    break
                
                # 保存会话和结果
                self._save_session()
                self._save_results()
        
        except KeyboardInterrupt:
            print("\n\n评估被中断")
        
        finally:
            # 最终保存
            self._save_session()
            self._save_results()
            
            # 显示统计信息
            self._print_final_statistics()


def main():
    parser = argparse.ArgumentParser(description='RAG 评估结果人工复核工具')
    parser.add_argument('--input_file', required=True, 
                        help='评估结果输入文件 (来自 evaluation.py 的输出)')
    parser.add_argument('--judge_results_file', required=True,
                        help='人工评估结果输出文件')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.input_file).exists():
        print(f"错误: 输入文件不存在: {args.input_file}")
        sys.exit(1)
    
    # 创建输出目录
    output_dir = Path(args.judge_results_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 启动人工评估工具
    judge = ManualJudge(args.input_file, args.judge_results_file)
    judge.run()


if __name__ == "__main__":
    main()