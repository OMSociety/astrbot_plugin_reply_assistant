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

    def __init__(self, config: dict):
        self.config = config or {}
        self._init_length_config()
        self._init_symbol_config()
        self._init_other_config()
    
    def _init_length_config(self):
        """初始化长度配置"""
        # 兼容不同名称的配置项
        self.min_segment_length = self._safe_int("min_segment_length", self._safe_int("min_length", 20))
        self.max_segment_length = self._safe_int("max_segment_length", self._safe_int("max_length", 50))
        
        if self.min_segment_length > self.max_segment_length:
            self.min_segment_length = self.max_segment_length
        
        # 其他长度相关配置
        self.enable_history_saving = bool(self.config.get("enable_history_saving", True))
        self.debug_mode = bool(self.config.get("debug_mode", False))
    
    def _init_symbol_config(self):
        """初始化分段符号配置"""
        raw_symbols = self.config.get("split_symbols")
        if not isinstance(raw_symbols, list) or len(raw_symbols) == 0:
            raw_symbols = ["\n\n", "\n", "。", "！", "？", "；", "……", ".", "!", "?", ";", "」", "、", "，", ","]
        
        self.split_symbols = []
        for s in raw_symbols:
            if isinstance(s, str):
                cleaned_s = s.replace("\\n", "\n").strip("\r")
                if cleaned_s:
                    self.split_symbols.append(cleaned_s)
        
        if not self.split_symbols:
            self.split_symbols = ["\n\n", "\n", "。", "！", "？"]
        
        self.keep_symbol = bool(self.config.get("keep_symbol", True))
    
    def _init_other_config(self):
        """初始化其他配置"""
        # 排除关键词和正则表达式
        exclude_kw = self.config.get("exclude_keywords", [])
        self.exclude_keywords = exclude_kw if isinstance(exclude_kw, list) else []
        
        exclude_patterns = self.config.get("exclude_patterns", [])
        self.exclude_patterns = exclude_patterns if isinstance(exclude_patterns, list) else []
        
        # 替换开关
        self.enable_emoji_replace = bool(self.config.get("enable_emoji_replace", False))
        self.enable_character_replace = bool(self.config.get("enable_character_replace", False))
        self.enable_markdown_clean = bool(self.config.get("enable_markdown_clean", False))
        
        # 替换规则
        emoji_replacements = self.config.get("emoji_replacements", {})
        self.emoji_replacements = emoji_replacements if isinstance(emoji_replacements, dict) else {}
        
        character_replacements = self.config.get("character_replacements", {})
        self.character_replacements = character_replacements if isinstance(character_replacements, dict) else {}
        
        # 旧配置兼容
        self.enable_string_replace = bool(self.config.get("enable_string_replace", True))
        self.enable_markdown_replace = bool(self.config.get("enable_markdown_replace", True))
        
        self.string_replacements = self._parse_replacements(
            self.config.get("string_replacements", [])
        )
        self.markdown_replacements = self._parse_replacements(
            self.config.get("markdown_replacements", [])
        )
    
    
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
            "min_segment_length": self.min_segment_length,
            "max_segment_length": self.max_segment_length,
            "enable_history_saving": self.enable_history_saving,
            "debug_mode": self.debug_mode,
            "split_symbols": self.split_symbols,
            "keep_symbol": self.keep_symbol,
            "exclude_keywords": self.exclude_keywords,
            "exclude_patterns": self.exclude_patterns,
            "enable_emoji_replace": self.enable_emoji_replace,
            "enable_character_replace": self.enable_character_replace,
            "enable_markdown_clean": self.enable_markdown_clean,
            "emoji_replacements": self.emoji_replacements,
            "character_replacements": self.character_replacements,
            "enable_string_replace": self.enable_string_replace,
            "enable_markdown_replace": self.enable_markdown_replace,
            "string_replacements": self.string_replacements,
            "markdown_replacements": self.markdown_replacements,
        }
