"""AstrBot 分段回复插件"""
import re
import os
from typing import List
from astrbot import logger
from astrbot.core.star import Context, Star
from astrbot.core.star.regist import hook_mark, schedule_mark
from dataclasses import dataclass
from .config_manager import SegmentConfigManager

# ========== 分段历史记录 ==========
_segment_history: dict[str, List[str]] = {}

def _clear_segment_history(session_id: str):
    _segment_history.pop(session_id, None)

@dataclass
class SegmentResult:
    """分段结果数据类"""
    segments: List[str]
    is_full: bool = False  # 是否为完整未分段内容

class CustomSegmentReplyPlugin(Star):
    """
    本地规则智能分段插件

    通过自定义字数、标点优先级、超长降级等规则实现智能分段，零成本更稳定
    """

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.cfg = SegmentConfigManager(config) if config else None
        logger.info("[分段插件] 插件初始化完成")

    def _apply_replacements(self, text: str) -> tuple[str, int]:
        """
        对文本应用所有替换规则（根据开关决定启用哪些）

        Args:
            text: 原始文本

        Returns:
            tuple: (处理后的文本, 替换次数)
        """
        total_count = 0
        processed = text

        # 1. 字符串替换
        if self.cfg.enable_string_replace:
            for pattern, replacement, is_regex in self.cfg.string_replacements:
                try:
                    if is_regex:
                        processed, count = re.subn(pattern, replacement, processed)
                        total_count += count
                    else:
                        count = processed.count(pattern)
                        if count > 0:
                            processed = processed.replace(pattern, replacement)
                            total_count += count
                except Exception as e:
                    logger.warning(f"[分段插件] 字符串替换失败: {pattern} -> {replacement}: {e}")


        # 2. Markdown 替换
        if self.cfg.enable_markdown_replace:
            for pattern, replacement, is_regex in self.cfg.markdown_replacements:
                try:
                    if is_regex:
                        processed, count = re.subn(pattern, replacement, processed)
                        total_count += count
                    else:
                        count = processed.count(pattern)
                        if count > 0:
                            processed = processed.replace(pattern, replacement)
                            total_count += count
                except Exception as e:
                    logger.warning(f"[分段插件] Markdown替换失败: {pattern} -> {replacement}: {e}")

        return processed, total_count

    def _check_exclude(self, segment: str) -> bool:
        """
        检查分段是否匹配排除规则

        Args:
            segment: 待检查的分段

        Returns:
            bool: 如果匹配排除规则返回 True
        """
        # 检查排除关键词
        for keyword in self.cfg.exclude_keywords:
            if keyword in segment:
                return True

        # 检查排除正则
        for pattern in self.cfg.exclude_patterns:
            try:
                if re.search(pattern, segment):
                    return True
            except Exception as e:
                logger.warning(f"[分段插件] 排除正则匹配失败: {pattern}: {e}")
        return False

    def _find_breakpoints(self, text: str) -> List[tuple]:
        """
        查找所有潜在断点

        Args:
            text: 处理后的文本

        Returns:
            List[tuple]: [(位置, 符号, 符号优先级), ...]，按位置排序
        """
        breakpoints = []
        for symbol in self.cfg.split_symbols:
            start = 0
            while True:
                pos = text.find(symbol, start)
                if pos == -1:
                    break
                breakpoints.append((pos + len(symbol), symbol))
                start = pos + len(symbol)


        # 按位置排序
        breakpoints.sort(key=lambda x: x[0])
        return breakpoints

    def segment_reply(self, text: str, session_id: str) -> SegmentResult:
        """
        对文本进行智能分段

        Args:
            text: 原始/待分段的文本
            session_id: 会话ID（用于历史记录）


        Returns:
            SegmentResult: 分段结果
        """
        # 处理替换
        text, _ = self._apply_replacements(text)

        # 记录历史并清理
        _clear_segment_history(session_id)

        # 空文本处理
        if not text or not text.strip():
            return SegmentResult(segments=[text.strip()])

        # 整体检查：如果文本本身就小于等于最大长度，直接返回
        if len(text) <= self.cfg.max_length:
            return SegmentResult(segments=[text], is_full=True)

        # 查找断点
        breakpoints = self._find_breakpoints(text)

        # 遍历断点，生成最终分段
        segments = []
        segment_start = 0
        i = 0
        while i < len(breakpoints):
            pos, symbol = breakpoints[i]
            # 当前分段长度 = 断点位置 - 分段起始位置
            current_len = pos - segment_start

            if current_len >= self.cfg.min_length:
                segment = text[segment_start:pos]

                # 检查是否需要排除
                if self._check_exclude(segment):
                    i += 1
                    continue

                segments.append(segment)
                segment_start = pos

                # 达到硬上限时停止，剩余部分单独成段
                if len(segments) >= self.cfg.hard_max_limit:
                    remaining = text[segment_start:]
                    if remaining:
                        segments.append(remaining)
                    return SegmentResult(segments=segments)

            i += 1

        # 处理剩余内容
        if segment_start < len(text):
            remaining = text[segment_start:]
            if remaining and not remaining.isspace():
                # 如果上一段太短，合并
                if (segments and len(segments[-1]) < self.cfg.short_tail_threshold
                    and self.cfg.merge_short_tail):
                    segments[-1] += remaining
                else:
                    segments.append(remaining)

        # 硬上限兜底
        if len(segments) > self.cfg.hard_max_limit:
            # 合并超长部分
            overflow = segments[self.cfg.hard_max_limit:]
            if overflow:
                overflow_text = "".join(overflow)
                segments = segments[:self.cfg.hard_max_limit]
                if segments:
                    segments[-1] += overflow_text
                else:
                    segments.append(overflow_text[:self.cfg.hard_max_limit])
        if not segments:
            segments = [text]

        return SegmentResult(segments=segments)
