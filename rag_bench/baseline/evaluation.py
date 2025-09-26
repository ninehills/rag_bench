#!/usr/bin/env python3
"""
RAG 评测脚本
不依赖第三方库（如 ragas），自行实现评测指标
"""

import os
import json
import argparse
import statistics
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_fixed
from rouge import Rouge

from utils import load_questions_as_dict, save_json, setup_llm_cache

from dotenv import load_dotenv

load_dotenv()
# Langchain OpenAI 的BASE_URL配置和 openai sdk 的配置不同
os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_BASE_URL", "")

# 设置SQLite缓存
setup_llm_cache()


def calculate_string_similarity(golden_text: str, retrieved_text: str) -> float:
    """
    计算两个字符串的相似度 (使用ROUGE-L)
    
    Args:
        golden_text: 黄金标准文本
        retrieved_text: 检索到的文本
        
    Returns:
        ROUGE-L召回率分数 (0-1)，1表示黄金文本完全被检索文本覆盖
    """
    if not golden_text or not retrieved_text:
        return 0.0
    
    golden_clean = golden_text.strip()
    retrieved_clean = retrieved_text.strip()
    
    if golden_clean == retrieved_clean:
        return 1.0
    
    # 如果黄金文本是检索文本的子串，返回1.0
    if golden_clean in retrieved_clean:
        return 1.0
    
    # 智能分词：中文字符级，英文单词级，数字和标点保持原样
    def smart_tokenize(text: str) -> str:
        """智能分词：中文字符级分词，英文单词级分词"""
        import re
        tokens = []
        # 匹配模式：英文单词、数字、标点符号、中文字符
        pattern = r'[a-zA-Z]+|\d+\.?\d*|[^\w\s]|[\u4e00-\u9fff]'
        for match in re.finditer(pattern, text):
            token = match.group()
            # 如果是中文字符，保持单字符
            # 如果是英文单词或数字，保持完整
            tokens.append(token)
        return " ".join(tokens)
    
    golden_chars = smart_tokenize(golden_clean)
    retrieved_chars = smart_tokenize(retrieved_clean)
    
    rouge = Rouge()
    try:
        scores = rouge.get_scores(retrieved_chars, golden_chars, ignore_empty=True)
        return scores[0]["rouge-l"]["r"]  # 返回ROUGE-L召回率
    except Exception:
        return 0.0


@dataclass
class EvaluationSample:
    """评估样本数据结构"""
    id: str
    query: str
    answer: str
    golden_answer: str
    retrieved_documents: List[Dict[str, Any]]
    related_documents: List[Dict[str, Any]]  # 相关文档列表


@dataclass
class RetrievalMetrics:
    """检索指标"""
    page_recall: Dict[int, float]
    page_mrr: Dict[int, float]
    content_recall: Dict[int, float]
    content_mrr: Dict[int, float]
    
    def __init__(self, k_values: List[int]):
        self.page_recall = {k: 0.0 for k in k_values}
        self.page_mrr = {k: 0.0 for k in k_values}
        self.content_recall = {k: 0.0 for k in k_values}
        self.content_mrr = {k: 0.0 for k in k_values}


@dataclass
class GenerationMetrics:
    """生成质量指标"""
    correctness: float = 0.0
    completeness: float = 0.0
    faithfulness: float = 0.0


@dataclass
class EvaluationResults:
    """评估结果"""
    retrieval_metrics: RetrievalMetrics
    generation_metrics: GenerationMetrics
    sample_count: int
    detailed_results: List[Dict[str, Any]] = None


class RAGEvaluator:
    """RAG 系统评估器"""
    
    def __init__(self, k_values: List[int] = None, 
                 content_similarity_threshold: float = 0.8):
        """
        初始化评估器
        
        Args:
            k_values: 检索评估的K值列表，默认为[1, 3, 5, 10]
            content_similarity_threshold: 内容相似度阈值，默认为0.8
        """
        eval_llm_model = os.getenv("JUDGE_MODEL", "Qwen/Qwen3-14B")
        self.llm = ChatOpenAI(model=eval_llm_model, temperature=0.001)
        self.k_values = k_values or [1, 3, 5, 10]
        self.content_similarity_threshold = content_similarity_threshold
    
    def load_qa_results(self, qa_results_file: str) -> List[Dict[str, Any]]:
        """加载问答结果文件"""
        with open(qa_results_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_questions(self, questions_file: str) -> Dict[str, Dict[str, Any]]:
        """加载问题文件，返回以ID为键的字典"""
        return load_questions_as_dict(questions_file)
    
    def create_evaluation_samples(self, qa_results: List[Dict[str, Any]], 
                                questions: Dict[str, Dict[str, Any]]) -> List[EvaluationSample]:
        """创建评估样本，按照原始问题文件的顺序"""
        # 创建qa_results的索引字典，便于快速查找
        qa_results_dict = {result['id']: result for result in qa_results}
        
        samples = []
        # 按照原始问题文件的顺序遍历
        for question_id, question_data in questions.items():
            if question_id not in qa_results_dict:
                print(f"警告: 未找到问题ID {question_id} 的QA结果")
                continue
            
            result = qa_results_dict[question_id]
            sample = EvaluationSample(
                id=question_id,
                query=result['query'],
                answer=result['answer'],
                golden_answer=question_data.get('golden_answer', ''),
                retrieved_documents=result['documents'],
                related_documents=question_data.get('related_documents', [])
            )
            samples.append(sample)
        
        return samples
    
    def calculate_recall_at_k(self, retrieved_items: List[str], 
                            relevant_items: List[str], k: int) -> float:
        """计算 Recall@K (精确匹配)"""
        if not relevant_items:
            return 0.0
        
        retrieved_k = set(retrieved_items[:k])
        relevant_set = set(relevant_items)
        
        intersection = retrieved_k.intersection(relevant_set)
        return len(intersection) / len(relevant_set)
    
    def calculate_content_recall_at_k(self, retrieved_contents: List[str], 
                                    relevant_contents: List[str], k: int) -> float:
        """计算内容召回率@K (基于字符串相似度)"""
        if not relevant_contents:
            return 0.0
        
        retrieved_k = retrieved_contents[:k]
        matched_count = 0
        
        for relevant_content in relevant_contents:
            # 检查是否有任何检索到的内容与相关内容相似
            for retrieved_content in retrieved_k:
                similarity = calculate_string_similarity(
                    relevant_content, retrieved_content
                )
                if similarity >= self.content_similarity_threshold:
                    matched_count += 1
                    break  # 找到匹配就停止，避免重复计算
        
        return matched_count / len(relevant_contents)
    
    def calculate_mrr_at_k(self, retrieved_items: List[str], 
                         relevant_items: List[str], k: int) -> float:
        """计算 MRR@K (Mean Reciprocal Rank) - 精确匹配"""
        if not relevant_items:
            return 0.0
        
        relevant_set = set(relevant_items)
        
        for i, item in enumerate(retrieved_items[:k]):
            if item in relevant_set:
                return 1.0 / (i + 1)
        
        return 0.0
    
    def calculate_content_mrr_at_k(self, retrieved_contents: List[str], 
                                 relevant_contents: List[str], k: int) -> float:
        """计算内容MRR@K (基于字符串相似度)"""
        if not relevant_contents:
            return 0.0
        
        retrieved_k = retrieved_contents[:k]
        
        for i, retrieved_content in enumerate(retrieved_k):
            # 检查当前检索内容是否与任何相关内容匹配
            for relevant_content in relevant_contents:
                similarity = calculate_string_similarity(
                    relevant_content, retrieved_content
                )
                if similarity >= self.content_similarity_threshold:
                    return 1.0 / (i + 1)
        
        return 0.0
    
    def evaluate_retrieval_metrics(self, samples: List[EvaluationSample]) -> Tuple[RetrievalMetrics, List[Dict[str, Any]]]:
        """评估检索指标，返回汇总指标和详细结果"""
        page_recalls = {k: [] for k in self.k_values}
        page_mrrs = {k: [] for k in self.k_values}
        content_recalls = {k: [] for k in self.k_values}
        content_mrrs = {k: [] for k in self.k_values}
        
        detailed_results = []
        
        for sample in samples:
            # 提取检索到的页面和内容
            retrieved_pages = []
            retrieved_contents = []
            
            for doc in sample.retrieved_documents:
                page_id = f"{doc.get('source_file', '')}_page_{doc.get('page_no', 0)}"
                retrieved_pages.append(page_id)
                retrieved_contents.append(doc.get('content', '').strip())
            
            # 构建相关页面和内容列表
            related_pages = []
            related_contents = []
            
            for related_doc in sample.related_documents:
                if isinstance(related_doc, dict):
                    page_id = f"{related_doc.get('source_file', '')}_page_{related_doc.get('page_no', 0)}"
                    related_pages.append(page_id)
                    related_contents.append(related_doc.get('content', '').strip())
            
            # 为当前样本计算各个K值的指标
            sample_result = {
                'id': sample.id,
                'query': sample.query,
                'answer': sample.answer,
                'golden_answer': sample.golden_answer,
                'retrieved_documents': sample.retrieved_documents,
                'related_documents': sample.related_documents,
                'retrieval_metrics': {}
            }
            
            for k in self.k_values:
                page_recall = self.calculate_recall_at_k(retrieved_pages, related_pages, k)
                page_mrr = self.calculate_mrr_at_k(retrieved_pages, related_pages, k)
                
                page_recalls[k].append(page_recall)
                page_mrrs[k].append(page_mrr)
                
                # 内容级别指标 (基于字符串相似度)
                content_recall = self.calculate_content_recall_at_k(retrieved_contents, related_contents, k)
                content_mrr = self.calculate_content_mrr_at_k(retrieved_contents, related_contents, k)
                
                content_recalls[k].append(content_recall)
                content_mrrs[k].append(content_mrr)
                
                # 保存当前样本的指标
                sample_result['retrieval_metrics'][f'page_recall_at_{k}'] = page_recall
                sample_result['retrieval_metrics'][f'page_mrr_at_{k}'] = page_mrr
                sample_result['retrieval_metrics'][f'content_recall_at_{k}'] = content_recall
                sample_result['retrieval_metrics'][f'content_mrr_at_{k}'] = content_mrr
            
            detailed_results.append(sample_result)
        
        # 计算平均值
        metrics = RetrievalMetrics(self.k_values)
        for k in self.k_values:
            metrics.page_recall[k] = statistics.mean(page_recalls[k]) if page_recalls[k] else 0.0
            metrics.page_mrr[k] = statistics.mean(page_mrrs[k]) if page_mrrs[k] else 0.0
            metrics.content_recall[k] = statistics.mean(content_recalls[k]) if content_recalls[k] else 0.0
            metrics.content_mrr[k] = statistics.mean(content_mrrs[k]) if content_mrrs[k] else 0.0
        
        return metrics, detailed_results
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def evaluate_correctness(self, query: str, answer: str, golden_answer: str) -> bool:
        """评估答案正确性"""
        prompt = f"""你是一个专业的评估专家，需要评估AI系统回答的正确性。

<task_description>
请仔细比较AI回答和标准答案，判断AI回答是否在事实上与标准答案一致。
评估时需要关注：
1. 事实准确性 - 核心事实是否正确
2. 逻辑一致性 - 推理逻辑是否合理
3. 关键信息 - 重要信息点是否正确
</task_description>

<question>
{query}
</question>

<ai_answer>
{answer}
</ai_answer>

<golden_answer>
{golden_answer}
</golden_answer>

<instructions>
请仔细分析AI回答与标准答案的一致性。
如果AI回答在事实上与标准答案一致（允许表述差异但事实完全正确），请输出：<result>是</result>
如果AI回答在事实上与标准答案不一致或存在错误，请输出：<result>否</result>
</instructions>

<examples>
- "100美金" 和 "100-200美金" 为不一致。
</examples>

请给出你的判断（<result>是</result>或<result>否</result>）："""
        
        try:
            response = self.llm.invoke(prompt)
            result = response.content.strip()  # 提取AIMessage的文本内容
            # 提取XML标签中的内容
            import re
            match = re.search(r'<result>(.*?)</result>', result, re.IGNORECASE)
            if match:
                judgment = match.group(1).strip()
                return "是" in judgment
            # 兜底逻辑
            return "是" in result or "正确" in result or "一致" in result
        except Exception as e:
            print(f"评估正确性时出错: {e}")
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def evaluate_completeness(self, query: str, answer: str, golden_answer: str) -> bool:
        """评估答案完整性"""
        prompt = f"""你是一个专业的评估专家，需要评估AI系统回答的完整性。

<task_description>
请评估AI回答是否完整地回答了问题，包含了标准答案中的所有重要信息点。
评估时需要关注：
1. 信息覆盖程度 - 是否包含所有关键信息点
2. 结构完整性 - 是否全面回答了问题的各个方面
3. 细节充分性 - 重要细节是否有遗漏
允许AI回答有额外的合理信息，但不能缺少标准答案中的核心内容。
</task_description>

<question>
{query}
</question>

<ai_answer>
{answer}
</ai_answer>

<golden_answer>
{golden_answer}
</golden_answer>

<instructions>
请仔细对比AI回答与标准答案，分析信息点的覆盖情况。
如果AI回答包含了标准答案中的所有主要信息点，请输出：<result>是</result>
如果AI回答缺少了标准答案中的重要信息点，请输出：<result>否</result>
</instructions>

请给出你的判断（<result>是</result>或<result>否</result>）："""
        
        try:
            response = self.llm.invoke(prompt)
            result = response.content.strip()  # 提取AIMessage的文本内容
            # 提取XML标签中的内容
            import re
            match = re.search(r'<result>(.*?)</result>', result, re.IGNORECASE)
            if match:
                judgment = match.group(1).strip()
                return "是" in judgment
            # 兜底逻辑
            return "是" in result or "完整" in result
        except Exception as e:
            print(f"评估完整性时出错: {e}")
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def evaluate_faithfulness(self, query: str, answer: str, golden_answer: str) -> bool:
        """评估答案忠诚度（是否存在幻觉）"""
        
        prompt = f"""你是一个专业的评估专家，需要评估AI系统回答的忠诚度。

<task_description>
请判断AI回答是否存在幻觉。

例子：
- AI回答是「我不知道」，正确答案是「1500元」，忠诚度为是。
- AI回答是「1000元」，正确答案是「1500元」，忠诚度为否。
- AI回答是「1500元」，正确答案是「1500元」，忠诚度为是。
</task_description>

<question>
{query}
</question>

<ai_answer>
{answer}
</ai_answer>

<golden_answer>
{golden_answer}
</golden_answer>

请给出你的判断（<result>是</result>或<result>否</result>）："""
        
        try:
            response = self.llm.invoke(prompt)
            result = response.content.strip()  # 提取AIMessage的文本内容
            # 提取XML标签中的内容
            import re
            match = re.search(r'<result>(.*?)</result>', result, re.IGNORECASE)
            if match:
                judgment = match.group(1).strip()
                return "是" in judgment
            # 兜底逻辑
            return "是" in result or "忠实" in result or "基于" in result
        except Exception as e:
            print(f"评估忠诚度时出错: {e}")
            return False
    
    def evaluate_metric_for_sample(self, sample: EvaluationSample, metric_type: str) -> bool:
        """评估单个样本的指定指标"""
        if metric_type == 'correctness':
            return self.evaluate_correctness(sample.query, sample.answer, sample.golden_answer)
        elif metric_type == 'completeness':
            return self.evaluate_completeness(sample.query, sample.answer, sample.golden_answer)
        elif metric_type == 'faithfulness':
            return self.evaluate_faithfulness(sample.query, sample.answer, sample.golden_answer)
        else:
            raise ValueError(f"未知的评估指标: {metric_type}")
    
    def evaluate_generation_metrics(self, samples: List[EvaluationSample], 
                                  batch_size: int = 9) -> Tuple[GenerationMetrics, List[Dict[str, Any]]]:
        """评估生成质量指标，返回汇总指标和详细结果"""
        # 为所有样本的所有指标创建任务列表
        tasks = []
        for sample in samples:
            for metric_type in ['correctness', 'completeness', 'faithfulness']:
                tasks.append((metric_type, sample))
        
        results = {'correctness': [], 'completeness': [], 'faithfulness': []}
        sample_results = {sample.id: {} for sample in samples}
        
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self.evaluate_metric_for_sample, sample, metric_type): (metric_type, sample)
                for metric_type, sample in tasks
            }
            
            # 获取结果
            for future in as_completed(future_to_task):
                metric_type, sample = future_to_task[future]
                try:
                    result = future.result()
                    results[metric_type].append(result)
                    sample_results[sample.id][metric_type] = result
                except Exception as e:
                    print(f"评估样本 {sample.id} 的 {metric_type} 时出错: {e}")
                    results[metric_type].append(False)
                    sample_results[sample.id][metric_type] = False
        
        # 构建详细结果
        detailed_results = []
        for sample in samples:
            sample_detail = {
                'id': sample.id,
                'query': sample.query,
                'answer': sample.answer,
                'golden_answer': sample.golden_answer,
                'retrieved_documents': sample.retrieved_documents,
                'related_documents': sample.related_documents,
                'generation_metrics': sample_results[sample.id]
            }
            detailed_results.append(sample_detail)
        
        # 计算平均值
        metrics = GenerationMetrics()
        metrics.correctness = sum(results['correctness']) / len(results['correctness']) if results['correctness'] else 0.0
        metrics.completeness = sum(results['completeness']) / len(results['completeness']) if results['completeness'] else 0.0
        metrics.faithfulness = sum(results['faithfulness']) / len(results['faithfulness']) if results['faithfulness'] else 0.0
        
        return metrics, detailed_results
    
    def evaluate(self, qa_results_file: str, questions_file: str, 
                only_retrieval: bool = False, batch_size: int = 3) -> EvaluationResults:
        """完整评估流程"""
        print("加载问答结果...")
        qa_results = self.load_qa_results(qa_results_file)
        
        print("加载问题数据...")
        questions = self.load_questions(questions_file)
        
        print("创建评估样本...")
        samples = self.create_evaluation_samples(qa_results, questions)
        print(f"创建了 {len(samples)} 个评估样本")
        
        print("评估检索指标...")
        retrieval_metrics, retrieval_detailed_results = self.evaluate_retrieval_metrics(samples)
        
        generation_metrics = GenerationMetrics()
        generation_detailed_results = []
        if not only_retrieval:
            print("评估生成质量指标...")
            generation_metrics, generation_detailed_results = self.evaluate_generation_metrics(samples, batch_size)
        
        # 合并详细结果
        detailed_results = []
        for i, retrieval_result in enumerate(retrieval_detailed_results):
            combined_result = retrieval_result.copy()
            if generation_detailed_results and i < len(generation_detailed_results):
                combined_result['generation_metrics'] = generation_detailed_results[i]['generation_metrics']
            else:
                combined_result['generation_metrics'] = {
                    'correctness': False,
                    'completeness': False,
                    'faithfulness': False
                }
            detailed_results.append(combined_result)
        
        return EvaluationResults(
            retrieval_metrics=retrieval_metrics,
            generation_metrics=generation_metrics,
            sample_count=len(samples),
            detailed_results=detailed_results
        )
    
    def print_results(self, results: EvaluationResults):
        """打印评估结果"""
        print("\n" + "="*50)
        print("评估结果")
        print("="*50)
        print(f"样本数量: {results.sample_count}")
        
        print("\n检索指标:")
        # Page级别指标
        for k in sorted(results.retrieval_metrics.page_recall.keys()):
            print(f"  Page Recall@{k:<2}: {results.retrieval_metrics.page_recall[k]:.4f}")
        
        for k in sorted(results.retrieval_metrics.page_mrr.keys()):
            print(f"  Page MRR@{k:<2}:    {results.retrieval_metrics.page_mrr[k]:.4f}")
        
        # Content级别指标
        for k in sorted(results.retrieval_metrics.content_recall.keys()):
            print(f"  Content Recall@{k:<2}: {results.retrieval_metrics.content_recall[k]:.4f}")
        
        for k in sorted(results.retrieval_metrics.content_mrr.keys()):
            print(f"  Content MRR@{k:<2}:    {results.retrieval_metrics.content_mrr[k]:.4f}")
        
        if results.generation_metrics.correctness > 0 or results.generation_metrics.completeness > 0:
            print("\n生成质量指标:")
            print(f"  正确性:   {results.generation_metrics.correctness:.4f}")
            print(f"  完整性:   {results.generation_metrics.completeness:.4f}")
            print(f"  忠诚度:   {results.generation_metrics.faithfulness:.4f}")
    
    def save_results(self, results: EvaluationResults, output_file: str):
        """保存评估结果到文件"""
        # 转换为字典格式
        retrieval_metrics_dict = {}
        
        # 添加page级别指标
        for k in results.retrieval_metrics.page_recall.keys():
            retrieval_metrics_dict[f'page_recall_at_{k}'] = results.retrieval_metrics.page_recall[k]
            retrieval_metrics_dict[f'page_mrr_at_{k}'] = results.retrieval_metrics.page_mrr[k]
            retrieval_metrics_dict[f'content_recall_at_{k}'] = results.retrieval_metrics.content_recall[k]
            retrieval_metrics_dict[f'content_mrr_at_{k}'] = results.retrieval_metrics.content_mrr[k]
        
        results_dict = {
            'sample_count': results.sample_count,
            'retrieval_metrics': retrieval_metrics_dict,
            'generation_metrics': {
                'correctness': results.generation_metrics.correctness,
                'completeness': results.generation_metrics.completeness,
                'faithfulness': results.generation_metrics.faithfulness,
            }
        }
        
        # 添加详细结果（如果存在）
        if results.detailed_results:
            results_dict['detailed_results'] = results.detailed_results
        
        save_json(results_dict, output_file)
        print(f"评估结果已保存到: {output_file}")
        if results.detailed_results:
            print(f"包含 {len(results.detailed_results)} 个样本的详细评估结果")


def main():
    parser = argparse.ArgumentParser(description='RAG 系统评估工具')
    parser.add_argument('--input_file', required=True, help='问题文件路径')
    parser.add_argument('--answer_file', required=True, help='问答结果文件路径')
    parser.add_argument('--eval_results_file', required=True, help='评估结果输出文件路径')
    parser.add_argument('--only_retrieval', action='store_true', help='仅评估检索指标')
    parser.add_argument('--batch_size', type=int, default=3, help='生成质量评估批处理大小')
    parser.add_argument('--k_values', nargs='+', type=int, default=[1, 3, 5, 10], 
                        help='检索评估的K值列表，默认为 [1, 3, 5, 10]')
    parser.add_argument('--content_similarity_threshold', type=float, default=0.7,
                        help='内容相似度阈值，默认为 0.7')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.answer_file).exists():
        print(f"错误: 问答结果文件不存在: {args.answer_file}")
        return
    
    if not Path(args.input_file).exists():
        print(f"错误: 问题文件不存在: {args.input_file}")
        return
    
    # 创建评估器
    evaluator = RAGEvaluator(
        k_values=args.k_values,
        content_similarity_threshold=args.content_similarity_threshold
    )
    
    # 执行评估
    results = evaluator.evaluate(
        qa_results_file=args.answer_file,
        questions_file=args.input_file,
        only_retrieval=args.only_retrieval,
        batch_size=args.batch_size
    )
    
    # 打印结果
    evaluator.print_results(results)
    
    # 保存结果
    evaluator.save_results(results, args.eval_results_file)


if __name__ == "__main__":
    main()