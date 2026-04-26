"""
分段插件配置管理器
负责配置的解析和验证
"""
import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


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

    def _init_length_config(self):
        """初始化长度相关配置"""
        self.min_length = max(1, self._safe_int("min_length", 20))
        self.max_length = max(self.min_length, self._safe_int("max_length", 50))

        if self.min_length > self.max_length:
            self.min_length = self.max_length

        self.allow_exceed_max = bool(self.config.get("allow_exceed_max", True))
        self.hard_max_limit = max(self.max_length, self._safe_int("hard_max_limit", 100))

        self.merge_short_tail = bool(self.config.get("merge_short_tail", True))
        self.short_tail_threshold = max(0, self._safe_int("short_tail_threshold", 8))

        if self.hard_max_limit < self.max_length:
            self.hard_max_limit = self.max_length * 2

    def _init_symbol_config(self):
        """初始化分段符号配置"""
        raw_symbols = self.config.get("split_symbols")
        if not isinstance(raw_symbols, list) or len(raw_symbols) == 0:
            raw_symbols = ["\n\n", "\n", "。", "！", "？", "；", "……", ".", "!", "?", ";", "」", "、", "，", ","]

        self.split_symbols = []
        seen = set()
        for s in raw_symbols:
            if not isinstance(s, str):
                continue
            cleaned_s = s.replace("\\n", "\n").strip("\r")
            if cleaned_s and cleaned_s not in seen:
                self.split_symbols.append(cleaned_s)
                seen.add(cleaned_s)

        if not self.split_symbols:
            self.split_symbols = ["\n\n", "\n", "。", "！", "？"]

        self.keep_symbol = bool(self.config.get("keep_symbol", False))

    def _init_replace_config(self):
        """初始化替换相关配置"""
        self.enable_string_replace = bool(self.config.get("enable_string_replace", False))
        self.string_replacements = self._parse_replacements(self.config.get("string_replacements", ["小笨蛋=>小可爱"]))

        self.enable_markdown_replace = bool(self.config.get("enable_markdown_replace", False))
        self.markdown_replacements = self._parse_replacements(self.config.get("markdown_replacements", []))

    def _init_exclude_config(self):
        """初始化排除规则配置"""
        exclude_kw = self.config.get("exclude_keywords", [])
        self.exclude_keywords = [kw for kw in exclude_kw if isinstance(kw, str)] if isinstance(exclude_kw, list) else []

        exclude_patterns = self.config.get("exclude_patterns", [])
        patterns = [p for p in exclude_patterns if isinstance(p, str)] if isinstance(exclude_patterns, list) else []
        self.exclude_patterns = patterns

        self.compiled_exclude_patterns = []
        for pattern in patterns:
            try:
                self.compiled_exclude_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"[配置] 排除正则无效，已忽略: {pattern}，错误: {e}")

    def _safe_int(self, key: str, default: int) -> int:
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
        if not isinstance(raw, list):
            return result

        for item in raw:
            if isinstance(item, dict) and "pattern" in item and "replacement" in item:
                pattern = item.get("pattern")
                replacement = item.get("replacement")
                if not isinstance(pattern, str) or not isinstance(replacement, str):
                    continue
                is_regex = bool(item.get("is_regex", False))
                result.append((pattern, replacement, is_regex))

            elif isinstance(item, str) and "=>" in item:
                parts = item.split("=>", 1)
                pattern = parts[0]
                replacement = parts[1]
                if pattern and replacement is not None:
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
