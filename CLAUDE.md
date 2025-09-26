# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a RAG (Retrieval-Augmented Generation) benchmark repository containing two main evaluation datasets:

1. **Chinese SimpleQA RAG** (`chinese_simpleqa_rag/`) - Chinese knowledge Q&A dataset (abandoned due to low retrieval difficulty)
2. **Prospectus QA** (`prospectus_qa/`) - Financial document Q&A using Chinese company prospectus PDFs

## Key Architecture

### Prospectus QA System
- **Data**: 80 Chinese company prospectus PDFs split between dev (5 PDFs) and validation (75 PDFs)
- **Evaluation**: Multi-dimensional assessment including factual, conditional, comparison, aggregation, multi-hop, and post-processing questions
- **Scoring**: CRAG-style evaluation with Perfect (1), Acceptable (0.5), Missing (0), and Incorrect (-1) scores
- **Retrieval Metrics**: PageRecall@N, PageMRR@N, ContentRecall@N, ContentMRR@N (N=1,3,5,10)

### Data Format

- Questions stored in JSONL format with `id`, `query`, `history`, `golden_answer`, and `related_documents`
- Results format includes `answer` and `documents` with `source_file`, `page_no`, `content`, and `score`
- Documents must not cross pages to enable proper evaluation

## Python Env

- MUST use uv to manage virtual environment
- MUST use uv to run Python scripts.

## Important Notes

- Both systems use OpenAI API-compatible models (configurable via .env)
- All document processing enforces no cross-page chunking for evaluation consistency
- The Chinese SimpleQA dataset was abandoned due to insufficient retrieval complexity
- Prospectus QA focuses on complex financial document understanding with multi-modal content (text, tables, charts)
- Evaluation uses both automated metrics and human judgment for comprehensive assessment