"""
分段插件配置管理器
负责配置的解析和验证
"""
import logging
from astrbot import logger
from typing import List, Tuple


class SegmentConfigManager:
    """
    配置管理类
    """

    def __init__(self, config: dict | None):
        self.config = config or {}
        self._init_length_config()
        self._init_symbol_config()
        self._init_replace_config()
        self._init_exclude_config()
        self._init_other_config()
    
    def _init_length_config(self):
        """初始化长度相关配置"""
        # 最小分段长度
        self.min_length = self._safe_int("min_length", 20)
        # 最大分段长度
        self.max_length = self._safe_int("max_length", 50)
        
        if self.min_length > self.max_length:
            self.min_length = self.max_length
        
        # 弹性延伸开关
        self.allow_exceed_max = bool(self.config.get("allow_exceed_max", True))
        # 绝对熔断上限
        self.hard_max_limit = self._safe_int("hard_max_limit", 100)
        
        # 短尾合并开关
        self.merge_short_tail = bool(self.config.get("merge_short_tail", True))
        # 短尾阈值
        self.short_tail_threshold = self._safe_int("short_tail_threshold", 8)
        
        # 确保 hard_max_limit >= max_length
        if self.hard_max_limit < self.max_length:
            self.hard_max_limit = self.max_length * 2
    
    def _init_symbol_config(self):
        """初始化分段符号配置"""
        raw_symbols = self.config.get("split_symbols")
        if not isinstance(raw_symbols, list) or len(raw_symbols) == 0:
            # 默认断句符号列表（按优先级排序）
            raw_symbols = ["\n\n", "\n", "。", "！", "？", "；", "……", ".", "!", "?", ";", "」", "、", "，", ","]
        
        self.split_symbols = []
        for s in raw_symbols:
            if isinstance(s, str):
                # 处理转义的换行符
                cleaned_s = s.replace("\\n", "\n").strip("\r")
                if cleaned_s:
                    self.split_symbols.append(cleaned_s)
        
        if not self.split_symbols:
            self.split_symbols = ["\n\n", "\n", "。", "！", "？"]
        
        # 是否保留断点符号
        self.keep_symbol = bool(self.config.get("keep_symbol", True))
    
    def _init_replace_config(self):
        """初始化替换相关配置"""
        # 字符串替换开关
        self.enable_string_replace = bool(self.config.get("enable_string_replace", True))
        
        # 解析字符串替换规则
        self.string_replacements = self._parse_replacements(
            self.config.get("string_replacements", [])
        )
        
        # Markdown 替换开关
        self.enable_markdown_replace = bool(self.config.get("enable_markdown_replace", True))
        
        # 解析 Markdown 替换规则
        self.markdown_replacements = self._parse_replacements(
            self.config.get("markdown_replacements", [])
        )
    
    def _init_exclude_config(self):
        """初始化排除规则配置"""
        # 排除关键词列表
        exclude_kw = self.config.get("exclude_keywords", [])
        self.exclude_keywords = exclude_kw if isinstance(exclude_kw, list) else []
        
        # 排除正则表达式列表
        exclude_patterns = self.config.get("exclude_patterns", [])
        self.exclude_patterns = exclude_patterns if isinstance(exclude_patterns, list) else []
    
    def _init_other_config(self):
        """初始化其他配置"""
        pass
    
    def _safe_int(self, key: str, default: int) -> int:
        """
        安全解析整数配置

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            int: 解析后的整数值
        """
        try:
            return int(self.config.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def _parse_replacements(self, raw: list) -> List[Tuple[str, str, bool]]:
        """
        解析替换规则

        支持格式：
        1. {"pattern": "x", "replacement": "y", "is_regex": true}
        2. "x=>y"  # 简单字符串替换

        Args:
            raw: 原始配置列表

        Returns:
            List[Tuple[str, str, bool]]: [(pattern, replacement, is_regex), ...]
        """
        result = []
        if isinstance(raw, list):
            for item in raw:
                # 格式1：字典格式
                if isinstance(item, dict) and "pattern" in item and "replacement" in item:
                    pattern = item["pattern"]
                    replacement = item["replacement"]
                    is_regex = bool(item.get("is_regex", False))
                    result.append((pattern, replacement, is_regex))
                    
                # 格式2：简单字符串 "x=>y"
                elif isinstance(item, str) and "=>" in item:
                    parts = item.split("=>", 1)
                    pattern = parts[0]
                    replacement = parts[1]
                    # 简单字符串不启用正则
                    result.append((pattern, replacement, False))
        return result
    
    def get_all_config(self) -> dict:
        """
        获取所有配置（供调试用）

        Returns:
            dict: 完整配置字典
        """
        return {
            # 长度配置
            "min_length": self.min_length,
            "max_length": self.max_length,
            "allow_exceed_max": self.allow_exceed_max,
            "hard_max_limit": self.hard_max_limit,
            "merge_short_tail": self.merge_short_tail,
            "short_tail_threshold": self.short_tail_threshold,
            # 符号配置
            "split_symbols": self.split_symbols,
            "keep_symbol": self.keep_symbol,
            # 排除配置
            "exclude_keywords": self.exclude_keywords,
            "exclude_patterns": self.exclude_patterns,
            # 替换配置
            "enable_string_replace": self.enable_string_replace,
            "string_replacements": self.string_replacements,
            "enable_markdown_replace": self.enable_markdown_replace,
            "markdown_replacements": self.markdown_replacements,
            # 其他
        }