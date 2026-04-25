"""
分段与文本替换插件

功能列表：
1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符替换（如将😀替换为🤪）
4. 支持 Markdown 格式清除
"""

import re
from typing import List

from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import on_decorating_result
from astrbot.api.all import Context, Star, AstrBotConfig, logger, register
from astrbot.api.message_components import Plain

from .config_manager import SegmentConfigManager


@register("astrbot_plugin_reply_assistant", "Slandre & Flandre", "分段与文本替换", "1.0.0")
class CustomSegmentReplyPlugin(Star):
    """
    消息分段处理插件

    Args:
        context: AstrBot 上下文
        config: 插件配置字典
    """

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.cfg = SegmentConfigManager(config or {})
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
                    logger.warning(f"[替换规则] 执行失败: {pattern} -> {replacement}, 错误: {e}")

        # 2. Markdown 替换（使用正则规则）
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
                    logger.warning(f"[Markdown替换] 执行失败: {pattern} -> {replacement}, 错误: {e}")

        return processed, total_count

    def _should_segment(self, text: str) -> bool:
        """
        判断是否应该对消息进行分段

        Args:
            text: 消息文本

        Returns:
            bool: True 表示应该分段，False 表示不应该
        """
        if len(text) <= self.cfg.min_length:
            return False

        for keyword in self.cfg.exclude_keywords:
            if keyword and keyword in text:
                return False

        for pattern in self.cfg.compiled_exclude_patterns:
            if pattern.search(text):
                return False

        return True

    def _segment_text(self, text: str) -> List[str]:
        """
        区间探测分段算法

        1. 在 [min_length, max_length] 区间内寻找最优断点（优先选区间内最晚断点）
        2. 启用弹性延伸时，向后扩展找下一个断点
        3. 超过 hard_max_limit 则强制切块
        4. 短尾过短时会合并到前一段

        Args:
            text: 原始文本

        Returns:
            List[str]: 分段后的文本列表
        """
        if not text:
            return []

        segments: List[str] = []

        if self.cfg.split_symbols:
            escaped_symbols = [re.escape(s) for s in self.cfg.split_symbols]
            symbol_pattern = "|".join(escaped_symbols)
        else:
            # 默认断句符号
            symbol_pattern = r"\n\n|\n|。|！|？"

        split_regex = re.compile(symbol_pattern)

        # 记录断点位置 + 具体命中的分隔符，用于 keep_symbol=False 时精准删掉
        breakpoints: List[tuple[int, str]] = []
        for match in split_regex.finditer(text):
            breakpoints.append((match.end(), match.group(0)))

        # 无可分隔符时按 hard_max_limit 直接分块，不丢数据
        if not breakpoints:
            for start in range(0, len(text), self.cfg.hard_max_limit):
                seg = text[start:start + self.cfg.hard_max_limit]
                if seg:
                    segments.append(seg)
            return segments

        segment_start = 0

        while segment_start < len(text):
            range_start = segment_start + self.cfg.min_length
            range_end = segment_start + self.cfg.max_length

            best_breakpoint = None
            matched_symbol = None

            # 在 [range_start, range_end] 内找“最晚”断点（让每段尽量长）
            window_breaks = [
                (bp, symbol)
                for bp, symbol in breakpoints
                if range_start <= bp <= range_end
            ]
            if window_breaks:
                best_breakpoint, matched_symbol = window_breaks[-1]

            # 区间内没断点且允许弹性延伸：继续向后找第一个
            if best_breakpoint is None and self.cfg.allow_exceed_max:
                exceed_breaks = [
                    (bp, symbol)
                    for bp, symbol in breakpoints
                    if range_end < bp <= segment_start + self.cfg.hard_max_limit
                ]
                if exceed_breaks:
                    best_breakpoint, matched_symbol = exceed_breaks[0]

            # 超限/找不到断点，按硬上限强制切块
            if best_breakpoint is None:
                forced_end = min(segment_start + self.cfg.hard_max_limit, len(text))
                segment = text[segment_start:forced_end].rstrip()
                if segment:
                    segments.append(segment)
                segment_start = forced_end
                continue

            segment = text[segment_start:best_breakpoint]
            if not self.cfg.keep_symbol and matched_symbol:
                if segment.endswith(matched_symbol):
                    segment = segment[: -len(matched_symbol)]
                segment = segment.rstrip()
            if segment:
                segments.append(segment)

            segment_start = best_breakpoint

        if self.cfg.merge_short_tail and len(segments) >= 2:
            last_segment = segments[-1]
            if len(last_segment) <= self.cfg.short_tail_threshold:
                segments[-2] = (segments[-2] + last_segment).rstrip()
                segments.pop()

        return segments

    @on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """
        消息发送前处理钩子 - 在 bot 输出消息之前拦截并处理

        Args:
            event: 消息事件
        """
        result = event.get_result()
        if result is None or not result.chain:
            return

        new_chain = []

        for comp in result.chain:
            if not isinstance(comp, Plain):
                new_chain.append(comp)
                continue

            text = comp.text
            if not text.strip():
                new_chain.append(comp)
                continue

            processed_text, replace_count = self._apply_replacements(text)

            if not self._should_segment(processed_text):
                if replace_count > 0:
                    comp.text = processed_text
                new_chain.append(comp)
                continue

            segments = self._segment_text(processed_text)
            if len(segments) <= 1:
                if replace_count > 0:
                    comp.text = processed_text
                new_chain.append(comp)
                continue

            logger.info(
                f"[分段插件] 处理完成，原文长度 {len(text)}，替换 {replace_count} 处，分段 {len(segments)} 段"
            )

            for segment in segments:
                if segment == "":
                    continue
                new_chain.append(Plain(segment))

        result.chain = new_chain

    async def terminate(self):
        """
        插件卸载时调用的清理方法（当前无需清理）
        """
        pass
