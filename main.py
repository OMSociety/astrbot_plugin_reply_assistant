"""
分段与文本替换插件

功能列表：
1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符替换（如将😀替换为🤪）
4. 支持 Markdown 格式清除
"""

import asyncio
import json
import random
import re
from typing import List

from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import on_decorating_result
from astrbot.api.all import Context, Star, AstrBotConfig, logger, register
from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain

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

            # 防止越界
            if range_start > len(text):
                range_start = len(text)
            if range_end > len(text):
                range_end = len(text)

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

    def _calculate_delay(self, prev_seg: str, curr_seg: str) -> float:
        """
        根据配置计算发送延迟

        Args:
            prev_seg: 前一段文本
            curr_seg: 当前要发送的文本

        Returns:
            float: 延迟秒数
        """
        delay_range = self.cfg.random_delay_range
        if isinstance(delay_range, list) and len(delay_range) >= 2:
            delay_min = float(delay_range[0])
            delay_max = float(delay_range[1])
        else:
            delay_min, delay_max = 1.0, 3.0

        if delay_min > delay_max:
            delay_min, delay_max = delay_max, delay_min

        # 使用正态分布生成随机延迟
        mean = (delay_min + delay_max) / 2
        std = max((delay_max - delay_min) / 6, 1e-6)
        return max(delay_min, min(delay_max, random.gauss(mean, std)))

    async def _set_typing(self, event: AstrMessageEvent, typing: bool):
        """
        向平台发送"正在输入"状态

        Args:
            event: 消息事件
            typing: 是否显示正在输入
        """
        try:
            if event.get_platform_name() != "aiocqhttp":
                return
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            if not isinstance(event, AiocqhttpMessageEvent):
                return
            user_id = event.message_obj.sender.user_id
            if not user_id:
                return
            await event.bot.api.call_action(
                "set_input_status",
                user_id=user_id,
                event_type=1 if typing else 0,
            )
        except Exception:
            pass

    async def _save_to_conversation_history(self, event: AstrMessageEvent, content: str):
        """
        将分段合并后的完整回复写入对话历史

        Args:
            event: 消息事件
            content: 完整的分段内容
        """
        try:
            conv_mgr = self.context.conversation_manager
            if not conv_mgr:
                return

            umo = event.unified_msg_origin
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            if not curr_cid:
                return

            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                return

            try:
                history = json.loads(conversation.history) if isinstance(conversation.history, str) else conversation.history
            except (json.JSONDecodeError, TypeError):
                history = []

            user_content = event.message_str
            if user_content and (not history or history[-1].get("role") != "user"):
                history.append({"role": "user", "content": user_content})

            history.append({"role": "assistant", "content": content})

            await conv_mgr.update_conversation(
                unified_msg_origin=umo,
                conversation_id=curr_cid,
                history=history,
            )
        except Exception as e:
            logger.error(f"[分段插件] 保存对话历史失败: {e}")

    @on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """
        消息发送前处理钩子 - 在 bot 输出消息之前拦截并处理
        分段内容通过 event.send() 逐条发送

        Args:
            event: 消息事件
        """
        result = event.get_result()
        if result is None or not result.chain:
            return

        # 收集需要处理的纯文本内容
        segments_to_send: List[str] = []
        other_components: List[Plain] = []

        for comp in result.chain:
            if not isinstance(comp, Plain):
                other_components.append(comp)
                continue

            text = comp.text
            if not text.strip():
                other_components.append(comp)
                continue

            processed_text, replace_count = self._apply_replacements(text)

            if not self._should_segment(processed_text):
                if replace_count > 0:
                    comp.text = processed_text
                other_components.append(comp)
                continue

            segments = self._segment_text(processed_text)
            if len(segments) <= 1:
                if replace_count > 0:
                    comp.text = processed_text
                other_components.append(comp)
                continue

            # 需要分段的内容
            segments_to_send.extend(segments)
            logger.info(
                f"[分段插件] 处理完成，原文长度 {len(text)}，替换 {replace_count} 处，分段 {len(segments)} 段"
            )

        # 如果没有需要分段的内容，直接返回（使用原始 chain）
        if not segments_to_send:
            return

        # 有分段内容需要发送
        # 先收集所有文本分段
        all_text_segments = segments_to_send.copy()
        if not all_text_segments:
            return

        first_segment = all_text_segments[0]
        remaining_segments = all_text_segments[1:] if len(all_text_segments) > 1 else []

        # 设置 result.chain：第一条分段 + 非文本组件（图片等）
        if other_components:
            result.chain = [Plain(first_segment)] + other_components
        else:
            result.chain = [Plain(first_segment)]

        # 构建完整内容用于保存对话历史
        full_text = first_segment + ("\n\n" + "\n\n".join(remaining_segments) if remaining_segments else "")

        # 逐条发送剩余分段
        if remaining_segments:
            await self._set_typing(event, True)
            for i, segment in enumerate(remaining_segments):
                if i > 0:
                    delay = self._calculate_delay(remaining_segments[i - 1], segment)
                    await asyncio.sleep(delay)
                await self._set_typing(event, True)
                await event.send(MessageChain().message(segment))
                await self._set_typing(event, False)
            await self._set_typing(event, False)

        # 保存完整的分段内容到对话历史
        if full_text:
            await self._save_to_conversation_history(event, full_text)

        logger.info(f"[分段插件] 分段回复完成，共 {len(remaining_segments) + 1} 段")

    async def terminate(self):
        """
        插件卸载时调用的清理方法（当前无需清理）
        """
        pass
