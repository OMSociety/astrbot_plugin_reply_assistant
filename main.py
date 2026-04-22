"""
分段与文本替换插件

功能列表：
1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符替换（如将😀替换为🤪）
4. 支持 Markdown 格式移除
5. 保存分段内容到对话历史
"""

import re
import json
from typing import List

from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import on_decorating_result
from astrbot.api.all import Context, Star, register, AstrBotConfig, logger
from astrbot.api.message_components import Plain

from .config_manager import SegmentConfigManager

@register("astrbot_plugin_custome_segment_reply", "Slandre & Flandre", "分段与文本替换", "1.0.0")
class CustomSegmentReplyPlugin(Star):
    """
    消息分段处理插件

    Args:
        context: AstrBot 上下文
        config: 插件配置字典
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = SegmentConfigManager(config)
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

        # 1. 表情替换
        if self.cfg.enable_emoji_replace:
            for old_emoji, new_emoji in self.cfg.emoji_replacements.items():
                count = processed.count(old_emoji)
                if count > 0:
                    processed = processed.replace(old_emoji, new_emoji)
                    total_count += count

        # 2. 字符替换
        if self.cfg.enable_character_replace:
            for old_char, new_char in self.cfg.character_replacements.items():
                count = processed.count(old_char)
                if count > 0:
                    processed = processed.replace(old_char, new_char)
                    total_count += count

        # 3. Markdown 清理
        if self.cfg.enable_markdown_clean:
            # 移除 Markdown 链接
            processed, link_count = re.subn(r'\[([^\]]+)\]\([^)]+\)', r'\1', processed)
            total_count += link_count

            # 移除 Markdown 图片
            processed, img_count = re.subn(r'!\[([^\]]*)\]\([^)]+\)', '', processed)
            total_count += img_count

            # 移除 Markdown 格式标记
            processed, bold_count = re.subn(r'\*\*([^*]+)\*\*', r'\1', processed)
            total_count += bold_count
            processed, italic_count = re.subn(r'\*([^*]+)\*', r'\1', processed)
            total_count += italic_count
            processed, code_count = re.subn(r'`([^`]+)`', r'\1', processed)
            total_count += code_count

        # 4. 旧配置兼容 - 字符串替换
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

        # 5. 旧配置兼容 - Markdown 替换
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
        # 1. 检查是否超过最小分段长度
        if len(text) <= self.cfg.min_segment_length:
            return False

        # 2. 检查是否包含排除关键词
        for keyword in self.cfg.exclude_keywords:
            if keyword in text:
                return False

        # 3. 检查是否包含排除正则表达式
        for pattern in self.cfg.exclude_patterns:
            if re.search(pattern, text):
                return False

        return True

    def _segment_text(self, text: str) -> List[str]:
        """
        将文本按标点符号分段

        Args:
            text: 原始文本

        Returns:
            List[str]: 分段后的文本列表
        """
        # 使用用户配置的 split_symbols 构建正则
        if self.cfg.split_symbols:
            escaped_symbols = [re.escape(s) for s in self.cfg.split_symbols]
            symbol_class = ''.join(escaped_symbols)
            split_pattern = r'([' + symbol_class + ']+)'
            symbol_pattern = r'[' + symbol_class + ']+'
        else:
            split_pattern = r'([\n]+)'
            symbol_pattern = r'[\n]+'
        
        segments = re.split(split_pattern, text)
        
        # 合并分割符到前一段（根据 keep_symbol 配置决定是否保留符号）
        result = []
        i = 0
        while i < len(segments):
            if i + 1 < len(segments) and re.match(symbol_pattern, segments[i + 1]):
                if self.cfg.keep_symbol:
                    combined = segments[i] + segments[i + 1]
                    result.append(combined.strip())
                else:
                    result.append(segments[i].strip())
                i += 2
            elif segments[i].strip():
                result.append(segments[i].strip())
                i += 1
            else:
                i += 1

        # 如果分段后只有一段，或者某一段特别长，可能需要进一步分割
        final_segments = []
        for segment in result:
            if len(segment) > self.cfg.max_segment_length:
                sub_segments = [
                    segment[i:i + self.cfg.max_segment_length]
                    for i in range(0, len(segment), self.cfg.max_segment_length)
                ]
                final_segments.extend(sub_segments)
            else:
                final_segments.append(segment)

        return final_segments

    def _save_segment_history(self, original_text: str, segments: List[str], replace_count: int, event: AstrMessageEvent):
        """
        保存分段历史（如果需要）

        Args:
            original_text: 原始文本
            segments: 分段后的文本列表
            replace_count: 替换次数
            event: 消息事件（当前未使用，保留参数接口）
        """
        if not self.cfg.enable_history_saving:
            return

        try:
            if self.cfg.debug_mode:
                logger.debug(f"[分段历史] 原始: {original_text[:50]}..., 分段数: {len(segments)}, 替换: {replace_count}")
            else:
                logger.info(f"[分段历史] 原始: {original_text[:50]}..., 分段数: {len(segments)}, 替换: {replace_count}")
        except Exception as e:
            logger.warning(f"[分段历史] 保存失败: {e}")
    @on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """
        消息发送前处理钩子 - 在 bot 输出消息之前拦截并处理

        Args:
            event: 消息事件
        """
        # 获取 bot 即将发送的消息
        result = event.get_result()
        if result is None or not result.chain:
            return

        # 只处理包含 Plain 组件的消息
        plain_components = [
            (i, comp) for i, comp in enumerate(result.chain)
            if isinstance(comp, Plain)
        ]
        if not plain_components:
            return

        # 合并所有 Plain 文本进行处理
        full_text = "".join(comp.text for _, comp in plain_components)
        
        if not full_text.strip():
            return

        # 应用替换规则
        processed_text, replace_count = self._apply_replacements(full_text)

        # 判断是否需要分段
        if not self._should_segment(processed_text):
            # 不需要分段，合并所有 Plain 组件为一个
            if replace_count > 0:
                # 找到所有 Plain 组件，保留第一个并更新文本，其余删除
                first_plain_idx = plain_components[0][0]
                # 重新构建消息链：保留非 Plain 组件 + 处理后的文本
                new_chain = []
                has_plain = False
                for i, comp in enumerate(result.chain):
                    if isinstance(comp, Plain):
                        if not has_plain:
                            comp.text = processed_text
                            new_chain.append(comp)
                            has_plain = True
                        # 跳过其他 Plain 组件
                    else:
                        new_chain.append(comp)
                result.chain = new_chain
            return

        # 进行分段
        segments = self._segment_text(processed_text)

        # 保存历史记录
        self._save_segment_history(processed_text, segments, replace_count, event)

        # 记录处理结果
        logger.info(f"[分段插件] 文本替换执行，共处理 {replace_count} 处")

        # 构建新的消息链 - 用分段后的 Plain 组件替换原有 Plain
        new_chain = []
        for comp in result.chain:
            if isinstance(comp, Plain):
                continue  # 跳过原 Plain
            else:
                new_chain.append(comp)  # 保留其他组件（图片、at等）

        # 添加分段后的 Plain 组件
        for segment in segments:
            new_chain.append(Plain(segment))

        # 更新消息链
        result.chain = new_chain

    @staticmethod
    async def terminate():
        """
        插件卸载时调用的清理方法（当前无需清理）
        """
        pass
