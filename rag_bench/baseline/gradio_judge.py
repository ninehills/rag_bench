#!/usr/bin/env python3
"""
Gradio-based RAG 评估结果人工复核工具
人工只对自动评估结果进行复核，不重新评估
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import traceback

import gradio as gr

from utils import load_file, save_json


@dataclass
class AppState:
    """应用状态管理"""
    current_index: int = 0
    data: Dict[str, Any] = None
    ui_state: Dict[str, Any] = field(default_factory=dict)
    show_documents: bool = False
    show_statistics: bool = False


class GradioManualJudge:
    """Gradio版本的人工评估复核工具"""

    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file

        # 加载数据
        self.data = self._load_input_data()
        self.results = self._load_or_init_results()

        # 应用状态
        self.state = AppState(
            current_index=self._get_last_judged_index(),
            data=self.results
        )

        # 自定义CSS样式
        self.custom_css = """
        .gradio-container {
            max-width: none !important;
            width: 95vw !important;
            margin: 0 auto;
        }

        .contain {
            max-width: none !important;
        }

        .app {
            max-width: none !important;
        }

        .sample-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            background: #ffffff;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .comparison-panel {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin: 1rem 0;
        }

        .answer-box {
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 1rem;
            background: #f9fafb;
            min-height: 120px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
        }

        .golden-answer {
            background: #f0f9ff;
            border-color: #3b82f6;
        }

        .ai-answer {
            background: #f8fafc;
            border-color: #64748b;
        }

        .evaluation-metrics {
            display: flex;
            gap: 2rem;
            align-items: center;
            padding: 1rem;
            background: #f1f5f9;
            border-radius: 8px;
            margin: 1rem 0;
        }

        .metric-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .metric-pass {
            color: #10b981;
            font-weight: 600;
        }

        .metric-fail {
            color: #ef4444;
            font-weight: 600;
        }

        .metric-auto {
            color: #ef4444;
        }

        .metric-manual {
            color: #10b981;
            font-weight: 600;
        }

        .progress-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 12px 12px 0 0;
            margin-bottom: 0;
        }

        .progress-bar {
            height: 6px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 0.5rem;
        }

        .progress-fill {
            height: 100%;
            background: #10b981;
            border-radius: 3px;
            transition: width 0.3s ease;
        }

        .action-buttons {
            display: flex;
            gap: 1rem;
            justify-content: center;
            align-items: center;
            padding: 1.5rem;
            background: #f8fafc;
            border-radius: 0 0 12px 12px;
        }

        .btn-primary {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 0.75rem 2rem;
            border-radius: 8px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-primary:hover {
            background: #2563eb;
            transform: translateY(-1px);
        }

        .btn-success {
            background: #10b981;
            color: white;
        }

        .btn-success:hover {
            background: #059669;
        }

        .btn-secondary {
            background: #6b7280;
            color: white;
        }

        .btn-secondary:hover {
            background: #4b5563;
        }

        .document-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin: 0.5rem 0;
            background: #ffffff;
        }

        .document-header {
            padding: 1rem;
            background: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
            border-radius: 8px 8px 0 0;
        }

        .document-content {
            padding: 1rem;
            font-family: 'JetBrains Mono', Monaco, monospace;
            font-size: 13px;
            line-height: 1.5;
            background: #fafafa;
            max-height: 200px;
            overflow-y: auto;
        }

        .stats-panel {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.5rem;
        }

        .stats-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid #f1f5f9;
        }

        .stats-item:last-child {
            border-bottom: none;
        }

        .radio-group {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            margin: 0.5rem 0;
        }

        .sample-id {
            font-weight: 600;
            color: #1e40af;
            font-size: 1.1em;
        }

        .query-text {
            font-size: 1.1em;
            font-weight: 500;
            color: #1f2937;
            margin: 1rem 0;
            line-height: 1.6;
        }

        .reviewed-status {
            background: #d1fae5;
            border: 1px solid #10b981;
            color: #065f46;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-weight: 500;
        }

        .pending-status {
            background: #fef3c7;
            border: 1px solid #f59e0b;
            color: #92400e;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-weight: 500;
        }
        """

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
            results = self.data.copy()
            for item in results['detailed_results']:
                item['manual_judgment'] = {
                    'correctness': None,
                    'completeness': None,
                    'faithfulness': None,
                    'judge_time': None,
                    'notes': ""
                }
            return results

    def _get_last_judged_index(self) -> int:
        """获取最后一个已评估样本的索引，返回下一个待评估的索引"""
        for i, sample in enumerate(self.results['detailed_results']):
            manual = sample.get('manual_judgment', {})
            if manual.get('judge_time') is None:  # 未评估过
                return i
        return len(self.results['detailed_results']) - 1  # 全部评估完成，停留在最后一个

    def _save_results(self):
        """保存结果数据"""
        save_json(self.results, self.output_file)

    def _get_current_sample(self) -> Dict[str, Any]:
        """获取当前样本"""
        if 0 <= self.state.current_index < len(self.results['detailed_results']):
            return self.results['detailed_results'][self.state.current_index]
        return {}

    def _calculate_statistics(self) -> Dict[str, Any]:
        """计算统计信息"""
        total_samples = len(self.results['detailed_results'])
        judged_samples = 0

        # 用于计算质量指标（基于所有样本的自动评估）
        auto_correctness_count = 0
        auto_completeness_count = 0
        auto_faithfulness_count = 0

        # 用于计算人工复核后的指标和一致性
        manual_correctness_count = 0
        manual_completeness_count = 0
        manual_faithfulness_count = 0
        agree_count = 0

        for sample in self.results['detailed_results']:
            # 统计自动评估结果（所有样本）
            auto_metrics = sample.get('generation_metrics', {})
            if auto_metrics.get('correctness', False):
                auto_correctness_count += 1
            if auto_metrics.get('completeness', False):
                auto_completeness_count += 1
            if auto_metrics.get('faithfulness', False):
                auto_faithfulness_count += 1

            # 统计人工复核结果
            manual = sample.get('manual_judgment', {})
            if manual.get('judge_time') is not None:  # 已经过人工复核
                judged_samples += 1
                if manual.get('correctness'):
                    manual_correctness_count += 1
                if manual.get('completeness'):
                    manual_completeness_count += 1
                if manual.get('faithfulness'):
                    manual_faithfulness_count += 1

                # 检查是否与自动评估一致（三个维度都一致才算一致）
                if (manual.get('correctness') == auto_metrics.get('correctness', False) and
                    manual.get('completeness') == auto_metrics.get('completeness', False) and
                    manual.get('faithfulness') == auto_metrics.get('faithfulness', False)):
                    agree_count += 1

        return {
            'total_samples': total_samples,
            'judged_samples': judged_samples,
            'progress': judged_samples / total_samples * 100 if total_samples > 0 else 0,
            # 质量指标基于自动评估结果（所有样本）
            'auto_correctness_rate': auto_correctness_count / total_samples * 100 if total_samples > 0 else 0,
            'auto_completeness_rate': auto_completeness_count / total_samples * 100 if total_samples > 0 else 0,
            'auto_faithfulness_rate': auto_faithfulness_count / total_samples * 100 if total_samples > 0 else 0,
            # 人工复核后的质量指标
            'manual_correctness_rate': manual_correctness_count / judged_samples * 100 if judged_samples > 0 else 0,
            'manual_completeness_rate': manual_completeness_count / judged_samples * 100 if judged_samples > 0 else 0,
            'manual_faithfulness_rate': manual_faithfulness_count / judged_samples * 100 if judged_samples > 0 else 0,
            # 一致性分析
            'agreement_rate': agree_count / judged_samples * 100 if judged_samples > 0 else 0
        }

    def _format_documents(self, documents: List[Dict[str, Any]]) -> str:
        """格式化检索文档显示"""
        if not documents:
            return "无检索文档"

        formatted_docs = []
        for i, doc in enumerate(documents, 1):
            source = doc.get('source_file', '未知来源')
            page = doc.get('page_no', 0)
            score = doc.get('score', 0)
            content = doc.get('content', '')[:500]  # 限制长度
            if len(doc.get('content', '')) > 500:
                content += "..."

            doc_text = f"""**文档 {i}**: {source} (页码: {page}) | 相关度: {score}
```
{content}
```
"""
            formatted_docs.append(doc_text)

        return "\n\n".join(formatted_docs)

    def update_display(self) -> Tuple[str, str, str, str, str, str, str, str, str, str, str, str, str]:
        """更新显示内容"""
        sample = self._get_current_sample()
        if not sample:
            return ("", "", "", "", "", "", "", "", "", "", "", "", "")

        # 基本信息
        sample_id = sample.get('id', 'Unknown')
        query = sample.get('query', '')
        ai_answer = sample.get('answer', '')
        golden_answer = sample.get('golden_answer', '')

        # 自动评估结果和人工复核状态
        auto_metrics = sample.get('generation_metrics', {})
        auto_correctness = auto_metrics.get('correctness', False)
        auto_completeness = auto_metrics.get('completeness', False)
        auto_faithfulness = auto_metrics.get('faithfulness', False)

        # 人工复核结果
        manual = sample.get('manual_judgment', {})
        is_reviewed = manual.get('judge_time') is not None

        if is_reviewed:
            # 已复核：显示对比
            manual_correctness = manual.get('correctness', False)
            manual_completeness = manual.get('completeness', False)
            manual_faithfulness = manual.get('faithfulness', False)

            auto_result = f"""
🤖 **自动评估结果** vs 👤 **人工复核结果**

- **正确性**: <span style="color: red;">{('✅ 通过' if auto_correctness else '❌ 未通过')}</span> → <span style="color: green;">**{'✅ 通过' if manual_correctness else '❌ 未通过'}**</span>
- **完整性**: <span style="color: red;">{('✅ 通过' if auto_completeness else '❌ 未通过')}</span> → <span style="color: green;">**{'✅ 通过' if manual_completeness else '❌ 未通过'}**</span>
- **忠诚度**: <span style="color: red;">{('✅ 通过' if auto_faithfulness else '❌ 未通过')}</span> → <span style="color: green;">**{'✅ 通过' if manual_faithfulness else '❌ 未通过'}**</span>

<span style="color: green;">✓ 已完成人工复核</span>
            """
        else:
            # 未复核：只显示自动评估
            auto_result = f"""
🤖 **自动评估结果** (待复核)

- **正确性**: {'✅ 通过' if auto_correctness else '❌ 未通过'}
- **完整性**: {'✅ 通过' if auto_completeness else '❌ 未通过'}
- **忠诚度**: {'✅ 通过' if auto_faithfulness else '❌ 未通过'}

<span style="color: orange;">⚠️ 等待人工复核</span>
            """

        # 人工复核备注
        manual_notes = manual.get('notes', '')

        # 检索文档
        documents = sample.get('retrieved_documents', [])
        documents_text = self._format_documents(documents)

        # 统计信息
        stats = self._calculate_statistics()
        total_count = len(self.results['detailed_results'])
        progress_text = f"进度: {self.state.current_index + 1}/{total_count} | 已复核: {stats['judged_samples']}/{stats['total_samples']} ({stats['progress']:.1f}%)"

        statistics_text = f"""
📊 **评估统计**

**进度统计**
- 总样本数: {stats['total_samples']}
- 已完成复核: {stats['judged_samples']}
- 完成率: {stats['progress']:.1f}%

**自动评估质量指标** (基于所有样本)
- 正确性: {stats['auto_correctness_rate']:.1f}%
- 完整性: {stats['auto_completeness_rate']:.1f}%
- 忠诚度: {stats['auto_faithfulness_rate']:.1f}%

**人工复核质量指标** (基于已复核样本)
- 正确性: {stats['manual_correctness_rate']:.1f}%
- 完整性: {stats['manual_completeness_rate']:.1f}%
- 忠诚度: {stats['manual_faithfulness_rate']:.1f}%

**一致性分析**
- 与自动评估一致率: {stats['agreement_rate']:.1f}%
        """

        # 决定在Radio组件中显示什么值
        if is_reviewed:
            # 如果已复核，显示人工复核的结果
            display_correctness = manual.get('correctness')
            display_completeness = manual.get('completeness')
            display_faithfulness = manual.get('faithfulness')
        else:
            # 如果未复核，显示自动评估结果供用户确认
            display_correctness = auto_correctness
            display_completeness = auto_completeness
            display_faithfulness = auto_faithfulness

        return (
            progress_text,  # 进度信息
            f"**样本ID**: {sample_id}",  # 样本ID
            f"**问题**: {query}",  # 问题
            ai_answer,  # AI回答
            golden_answer,  # 标准答案
            auto_result,  # 自动评估结果vs人工复核对比
            statistics_text,  # 统计信息
            documents_text,  # 检索文档
            display_correctness,  # Radio显示值-正确性
            display_completeness,  # Radio显示值-完整性
            display_faithfulness,  # Radio显示值-忠诚度
            manual_notes,  # 备注
            f"当前第 {self.state.current_index + 1} 个样本，共 {total_count} 个 {'(已复核)' if is_reviewed else '(待复核)'}"  # 状态信息
        )

    def navigate_previous(self):
        """导航到上一个样本"""
        if self.state.current_index > 0:
            self.state.current_index -= 1
        return self.update_display()

    def navigate_next(self):
        """导航到下一个样本"""
        total_count = len(self.results['detailed_results'])
        if self.state.current_index < total_count - 1:
            self.state.current_index += 1
        return self.update_display()

    def submit_manual_evaluation(self, correctness, completeness, faithfulness, notes):
        """提交手动复核"""
        sample = self._get_current_sample()
        if not sample:
            return self.update_display()

        manual = sample['manual_judgment']

        # 允许重复修改，不检查是否已复核

        # 检查输入有效性
        if correctness is None or completeness is None or faithfulness is None:
            return self.update_display()

        manual['correctness'] = correctness
        manual['completeness'] = completeness
        manual['faithfulness'] = faithfulness
        manual['judge_time'] = datetime.now().isoformat()
        manual['notes'] = notes or ""

        self._save_results()

        # 自动跳转到下一个
        total_count = len(self.results['detailed_results'])
        if self.state.current_index < total_count - 1:
            self.state.current_index += 1

        return self.update_display()

    def create_interface(self):
        """创建Gradio界面"""
        with gr.Blocks(
            title="RAG Manual Judge Review",
            theme=gr.themes.Soft(primary_hue="blue", secondary_hue="gray"),
            css=self.custom_css
        ) as app:

            # 标题和进度
            gr.HTML("""
            <div class="progress-header">
                <h1 style="margin: 0; font-size: 1.5em;">🔍 RAG 评估结果人工复核工具</h1>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Gradio Manual Judge for RAG Evaluation Review</p>
            </div>
            """)

            progress_info = gr.HTML()

            # 主要内容区域 - 宽屏布局
            # 样本信息
            sample_id_display = gr.Markdown()
            query_display = gr.Markdown()

            # 答案对比
            gr.HTML("<h3>📄 答案对比</h3>")
            with gr.Row():
                with gr.Column():
                    gr.HTML("<h4>🤖 AI回答</h4>")
                    ai_answer_display = gr.Textbox(
                        interactive=False,
                        lines=8,
                        container=False
                    )
                with gr.Column():
                    gr.HTML("<h4>⭐ 标准答案</h4>")
                    golden_answer_display = gr.Textbox(
                        interactive=False,
                        lines=8,
                        container=False
                    )

            # 自动评估结果vs人工复核对比
            auto_eval_display = gr.Markdown()

            # 人工复核输入
            gr.HTML("<h3>👤 人工复核</h3>")
            gr.HTML("<p style='color: #666; margin-bottom: 1rem;'>请确认或修正评估结果</p>")
            with gr.Row():
                correctness_radio = gr.Radio(
                    choices=[True, False],
                    label="正确性",
                    type="value"
                )
                completeness_radio = gr.Radio(
                    choices=[True, False],
                    label="完整性",
                    type="value"
                )
                faithfulness_radio = gr.Radio(
                    choices=[True, False],
                    label="忠诚度",
                    type="value"
                )

            notes_input = gr.Textbox(
                label="复核备注 (可选)",
                lines=3,
                placeholder="请输入复核备注..."
            )

            # 导航和提交按钮
            with gr.Row():
                prev_btn = gr.Button("⬅️ 上一条", variant="secondary", size="lg")
                next_btn = gr.Button("下一条 ➡️", variant="secondary", size="lg")
                submit_btn = gr.Button("📝 提交复核", variant="primary", size="lg")

            # 统计信息和文档 - 放在下方
            with gr.Row():
                with gr.Column():
                    gr.HTML("<h3>📊 统计信息</h3>")
                    statistics_display = gr.Markdown()

                with gr.Column():
                    # 检索文档 (可折叠)
                    with gr.Accordion("📚 检索文档", open=False):
                        documents_display = gr.Markdown()

            # 状态信息
            status_info = gr.HTML()

            # 事件绑定
            prev_btn.click(
                fn=self.navigate_previous,
                outputs=[
                    progress_info, sample_id_display, query_display,
                    ai_answer_display, golden_answer_display, auto_eval_display,
                    statistics_display, documents_display,
                    correctness_radio, completeness_radio, faithfulness_radio, notes_input,
                    status_info
                ]
            )

            next_btn.click(
                fn=self.navigate_next,
                outputs=[
                    progress_info, sample_id_display, query_display,
                    ai_answer_display, golden_answer_display, auto_eval_display,
                    statistics_display, documents_display,
                    correctness_radio, completeness_radio, faithfulness_radio, notes_input,
                    status_info
                ]
            )

            submit_btn.click(
                fn=self.submit_manual_evaluation,
                inputs=[correctness_radio, completeness_radio, faithfulness_radio, notes_input],
                outputs=[
                    progress_info, sample_id_display, query_display,
                    ai_answer_display, golden_answer_display, auto_eval_display,
                    statistics_display, documents_display,
                    correctness_radio, completeness_radio, faithfulness_radio, notes_input,
                    status_info
                ]
            )

            # 页面加载时初始化显示
            app.load(
                fn=self.update_display,
                outputs=[
                    progress_info, sample_id_display, query_display,
                    ai_answer_display, golden_answer_display, auto_eval_display,
                    statistics_display, documents_display,
                    correctness_radio, completeness_radio, faithfulness_radio, notes_input,
                    status_info
                ]
            )

        return app

    def launch(self, host="0.0.0.0", port=7860, share=False):
        """启动应用"""
        app = self.create_interface()
        app.launch(
            server_name=host,
            server_port=port,
            share=share,
            show_error=True
        )


def main():
    parser = argparse.ArgumentParser(description='RAG 评估结果人工复核工具 - Gradio Web版')
    parser.add_argument('--input_file', required=True,
                        help='评估结果输入文件 (来自 evaluation.py 的输出)')
    parser.add_argument('--judge_results_file', required=True,
                        help='人工评估结果输出文件')
    parser.add_argument('--host', default='0.0.0.0',
                        help='服务器主机名 (默认: 0.0.0.0)')
    parser.add_argument('--port', default=7860, type=int,
                        help='服务器端口号 (默认: 7860)')
    parser.add_argument('--share', action='store_true',
                        help='是否创建公共分享链接')

    args = parser.parse_args()

    # 检查输入文件
    if not Path(args.input_file).exists():
        print(f"错误: 输入文件不存在: {args.input_file}")
        sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.judge_results_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 启动 Gradio 应用
        judge = GradioManualJudge(args.input_file, args.judge_results_file)
        print("🚀 启动 RAG Manual Judge Review 应用...")
        print(f"📁 输入文件: {args.input_file}")
        print(f"📁 输出文件: {args.judge_results_file}")
        print(f"🌐 访问地址: http://{args.host}:{args.port}")

        judge.launch(host=args.host, port=args.port, share=args.share)

    except Exception as e:
        print(f"启动失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()