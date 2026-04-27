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
import re

from astrbot.api.all import AstrBotConfig, Context, Star, logger, register
from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import on_decorating_result
from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .config_manager import SegmentConfigManager


@register(
    "astrbot_plugin_reply_assistant", "Slandre & Flandre", "分段与文本替换", "1.2.0"
)
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
                    logger.warning(
                        f"[替换规则] 执行失败: {pattern} -> {replacement}, 错误: {e}"
                    )

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
                    logger.warning(
                        f"[Markdown替换] 执行失败: {pattern} -> {replacement}, 错误: {e}"
                    )

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

    def _segment_text(self, text: str) -> list[str]:
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

        segments: list[str] = []

        escaped_symbols = [re.escape(s) for s in self.cfg.split_symbols]
        symbol_pattern = "|".join(escaped_symbols)

        split_regex = re.compile(symbol_pattern)

        # 记录断点位置 + 具体命中的分隔符，用于 keep_symbol=False 时精准删掉
        breakpoints: list[tuple[int, str]] = []
        for match in split_regex.finditer(text):
            breakpoints.append((match.end(), match.group(0)))

        # 无可分隔符时按 hard_max_limit 直接分块，不丢数据
        if not breakpoints:
            for start in range(0, len(text), self.cfg.hard_max_limit):
                seg = text[start : start + self.cfg.hard_max_limit]
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

    async def _set_typing(self, event: AstrMessageEvent, typing: bool):
        """向平台发送"正在输入"状态（多平台支持）"""
        try:
            platform = event.get_platform_name()

            # aiocqhttp (QQ)
            if platform == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                    AiocqhttpMessageEvent,
                )

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
                return

            # telegram
            if platform == "telegram":
                chat_id = event.message_obj.sender.user_id or event.message_obj.group_id
                if chat_id:
                    await event.bot.api.call_action(
                        "sendChatAction",
                        chat_id=chat_id,
                        action="typing" if typing else "cancel",
                    )
                return

            # discord
            if platform == "discord":
                try:
                    if typing and hasattr(event, "_discord_event"):
                        await event._discord_event.channel.trigger_typing()
                except Exception as e:
                    logger.debug(f"[ReplyAssistant] Discord typing 失败: {e}")
                return

            # 其他平台尝试通用方式
            if (
                typing
                and hasattr(event.bot, "api")
                and hasattr(event.bot.api, "call_action")
            ):
                try:
                    await event.bot.api.call_action("typing", {})
                except Exception:
                    pass

        except Exception:
            pass

    async def _save_to_conversation_history(
        self, event: AstrMessageEvent, content: str
    ):
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
                history = (
                    json.loads(conversation.history)
                    if isinstance(conversation.history, str)
                    else conversation.history
                )
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
        from astrbot.core.message.message_event_result import ResultContentType

        result = event.get_result()
        if result is None or not result.chain:
            return

        # 流式输出时跳过，避免重复发送
        if result.result_content_type == ResultContentType.STREAMING_FINISH:
            return

        # 按原始顺序收集：所有文本（包括分段后的）+ Image 类型组件
        plain_texts: list[str] = []
        image_components: list = []
        total_replace_count = 0

        for comp in result.chain:
            if not isinstance(comp, Plain):
                image_components.append(comp)
                continue

            text = comp.text
            if not text.strip():
                image_components.append(comp)
                continue

            processed_text, replace_count = self._apply_replacements(text)
            total_replace_count += replace_count

            if not self._should_segment(processed_text):
                # 不需要分段，直接追加到文本列表
                plain_texts.append(processed_text)
                continue

            segments = self._segment_text(processed_text)
            if not segments or (len(segments) == 1 and not segments[0].strip()):
                # 分段失败或只有空段，直接用原文本
                plain_texts.append(processed_text)
                continue

            if len(segments) == 1:
                # 分段后只有一段，直接追加
                plain_texts.append(segments[0])
                continue

            # 过滤空段，保留有效内容
            valid_segments = []
            for i, seg in enumerate(segments):
                stripped = seg.strip("\n\r")
                if stripped:
                    valid_segments.append(stripped)
            plain_texts.extend(valid_segments)
            logger.info(
                f"[分段插件] 处理完成，原文长度 {len(text)}，替换 {total_replace_count} 处，分段 {len(valid_segments)} 段"
            )

        # 如果没有文本内容，直接返回
        if not plain_texts:
            return

        # 构建完整内容用于保存对话历史
        full_text = "\n\n".join(plain_texts)

        # 先发送所有文本分段，再发送图片
        if self.cfg.enable_typing_indicator:
            await self._set_typing(event, True)
        for segment in plain_texts:
            await event.send(MessageChain().message(segment))
        if self.cfg.enable_typing_indicator:
            await self._set_typing(event, False)
        # 图片单独发，跟随在对话后（优先取 meme_manager 的表情包，否则用 result.chain 里的 Image）
        meme_images = event.get_extra("meme_manager_pending_images")
        pending_images = meme_images if meme_images else image_components
        if pending_images:
            await asyncio.sleep(0.3)
            await event.send(MessageChain(pending_images))
            event.set_extra("meme_manager_pending_images", None)

        # 保存完整的分段内容到对话历史
        if full_text:
            await self._save_to_conversation_history(event, full_text)

        # 清空 result.chain，防止框架重复发送
        result.chain = []

    async def terminate(self):
        """
        插件卸载时调用的清理方法（当前无需清理）
        """
        pass
