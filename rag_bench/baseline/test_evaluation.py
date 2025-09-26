#!/usr/bin/env python3
"""
评测脚本的单元测试
测试字符串相似度计算功能
"""

import unittest
from evaluation import calculate_string_similarity


class TestStringSimilarity(unittest.TestCase):
    """测试字符串相似度计算功能"""
    
    def test_identical_strings(self):
        """测试完全相同的字符串"""
        golden = "这是一个测试文本"
        retrieved = "这是一个测试文本"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)
    
    def test_empty_strings(self):
        """测试空字符串"""
        self.assertEqual(calculate_string_similarity("", "任何文本"), 0.0)
        self.assertEqual(calculate_string_similarity("任何文本", ""), 0.0)
        self.assertEqual(calculate_string_similarity("", ""), 0.0)
    
    def test_perfect_substring_match(self):
        """测试完美子串匹配"""
        golden = "江苏爱康太阳能2008年度无形资产投资1526.45万元"
        retrieved = "根据招股意向书显示，江苏爱康太阳能2008年度无形资产投资1526.45万元，这一数据来源于重大资本性支出部分。"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)
    
    def test_partial_match_high_overlap(self):
        """测试部分匹配但重叠度很高"""
        golden = "注册资本15000万元"
        retrieved = "江苏爱康太阳能科技股份有限公司注册资本为15000万元人民币"
        similarity = calculate_string_similarity(golden, retrieved)
        # 由于包含子串逻辑，这个会返回1.0
        self.assertEqual(similarity, 1.0)
    
    def test_partial_match_medium_overlap(self):
        """测试中等重叠的情况"""
        golden = "实际控制人邹承慧先生"
        retrieved = "公司法定代表人为邹承慧，同时也是公司的实际控制人"
        similarity = calculate_string_similarity(golden, retrieved)
        # 期望有中等的相似度
        self.assertGreater(similarity, 0.3)
        self.assertLess(similarity, 0.8)
    
    def test_low_overlap(self):
        """测试低重叠的情况"""
        golden = "2008年度无形资产投资1526.45万元"
        retrieved = "公司主要从事太阳能组件生产和销售业务"
        similarity = calculate_string_similarity(golden, retrieved)
        # 期望相似度很低
        self.assertLess(similarity, 0.3)
    
    def test_no_overlap(self):
        """测试完全不相关的文本"""
        golden = "财务数据显示"
        retrieved = "abcdefg xyz 123"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 0.0)
    
    def test_chinese_english_mixed(self):
        """测试中英文混合文本"""
        golden = "ERNIE-4.0-Turbo模型"
        retrieved = "本次评估使用ERNIE-4.0-Turbo模型进行问答质量评估，该模型具有较好的中文理解能力"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 应该检测到完整包含
    
    def test_table_content_match(self):
        """测试表格内容匹配"""
        golden = "无形资产投资 1,526.45"
        retrieved = """
        项目 2010年度 2009年度 2008年度
        股权投资支出 - 2,000.00 -
        固定资产投资 8,423.86 5,252.46 3,919.55
        无形资产投资 12,040.47 358.50 1,526.45
        合计 20,464.33 7,610.77 3,919.55
        """
        similarity = calculate_string_similarity(golden, retrieved)
        # 应该有较高的相似度，因为关键信息被包含
        self.assertGreater(similarity, 0.6)
    
    def test_number_precision_match(self):
        """测试数字精度匹配"""
        golden = "1526.45万元"
        retrieved = "投资金额为1,526.45万元人民币"
        similarity = calculate_string_similarity(golden, retrieved)
        # 数字格式略有不同，但应该有较高相似度
        self.assertGreater(similarity, 0.7)
    
    def test_whitespace_handling(self):
        """测试空白字符处理"""
        golden = "江苏爱康太阳能"
        retrieved = "  江苏爱康太阳能科技股份有限公司  "
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 应该检测到包含关系
    
    def test_order_sensitivity(self):
        """测试词序敏感性"""
        golden = "2008年度无形资产投资"
        retrieved = "无形资产投资2008年度数据"
        similarity = calculate_string_similarity(golden, retrieved)
        # ROUGE-L考虑词序，所以不应该是1.0，但应该有一定相似度
        self.assertGreaterEqual(similarity, 0.5)
        self.assertLess(similarity, 1.0)
    
    def test_case_sensitivity(self):
        """测试大小写敏感性（主要针对英文）"""
        golden = "PDF文件"
        retrieved = "这是一个pdf文件的内容"
        similarity = calculate_string_similarity(golden, retrieved)
        # 应该有一定的相似度，尽管大小写不同
        self.assertGreater(similarity, 0.3)


class TestChineseEnglishCompatibility(unittest.TestCase):
    """测试中英文兼容性"""
    
    def test_pure_english(self):
        """测试纯英文"""
        golden = "artificial intelligence model"
        retrieved = "This is an artificial intelligence model for testing"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 完全包含
    
    def test_pure_english_partial(self):
        """测试纯英文部分匹配"""
        golden = "machine learning algorithm"
        retrieved = "deep learning and machine learning techniques"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertGreater(similarity, 0.5)  # 部分匹配
    
    def test_chinese_english_mixed(self):
        """测试中英文混合"""
        golden = "使用ERNIE-4.0模型进行评估"
        retrieved = "本次实验使用ERNIE-4.0模型进行答案质量评估，效果良好"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 完全包含
    
    def test_english_numbers_chinese(self):
        """测试英文+数字+中文混合"""
        golden = "GDP增长率为3.5%"
        retrieved = "2023年中国GDP增长率为3.5%，超出预期"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 完全包含
    
    def test_technical_terms(self):
        """测试技术术语"""
        golden = "ROUGE-L评估指标"
        retrieved = "我们采用ROUGE-L评估指标来衡量文本相似度"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 完全包含
    
    def test_english_word_order(self):
        """测试英文词序"""
        golden = "natural language processing"
        retrieved = "processing of natural language"
        similarity = calculate_string_similarity(golden, retrieved)
        # 词序改变，应该有中等相似度
        self.assertGreater(similarity, 0.3)
        self.assertLess(similarity, 1.0)


class TestStringSimilarityEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def test_very_long_text(self):
        """测试很长的文本"""
        golden = "关键信息"
        retrieved = "这是一段很长的文本，" * 100 + "关键信息在这里，" + "后面还有很多内容。" * 100
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)  # 应该检测到包含关系
    
    def test_special_characters(self):
        """测试特殊字符"""
        golden = "投资金额：1,526.45万元（人民币）"
        retrieved = "根据资料显示，投资金额：1,526.45万元（人民币），符合预期。"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)
    
    def test_repeated_content(self):
        """测试重复内容"""
        golden = "重要信息"
        retrieved = "重要信息重要信息重要信息"
        similarity = calculate_string_similarity(golden, retrieved)
        self.assertEqual(similarity, 1.0)


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)