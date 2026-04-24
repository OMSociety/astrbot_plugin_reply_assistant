"""
分段与文本替换插件

功能列表：
1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符替换（如将😀替换为🤪）
4. 支持 Markdown 格式清除
5. 保存分段内容到对话历史
"""

import re
import json
from typing import List, Optional

from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import on_decorating_result
from astrbot.api.all import Context, Star, register, AstrBotConfig, logger
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
        # 1. 检查是否超过最小分段长度
        if len(text) <= self.cfg.min_length:
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
        区间探测分段算法
        
        1. 在 [min_length, max_length] 区间内寻找断点
        2. 启用弹性延伸时，向后扩展找下一个断点
        3. 超过 hard_max_limit 则强制截断
        4. 短尾合并
        
        Args:
            text: 原始文本
            
        Returns:
            List[str]: 分段后的文本列表
        """
        if not text:
            return []
        
        segments = []
        
        # 构建断点符号的正则模式，按优先级排序
        if self.cfg.split_symbols:
            escaped_symbols = [re.escape(s) for s in self.cfg.split_symbols]
            symbol_pattern = '|'.join(escaped_symbols)
        else:
            # 默认断句符号
            symbol_pattern = r'\n\n|\n|。|！|？'
        
        # 编译正则表达式
        split_regex = re.compile(symbol_pattern)
        
        # 寻找所有断点位置
        breakpoints = []
        for match in split_regex.finditer(text):
            # 断点位置是符号结束的位置
            breakpoints.append(match.end())
        
        if not breakpoints:
            # 没有断点，整个文本作为一段
            if len(text) > self.cfg.hard_max_limit:
                return [text[:self.cfg.hard_max_limit]]
            return [text]
        
        # 按符号长度降序排列断点（优先匹配长符号）
        breakpoints.sort()
        
        # 区间探测分段
        segment_start = 0
        
        while segment_start < len(text):
            # 计算区间边界
            range_start = segment_start + self.cfg.min_length
            range_end = segment_start + self.cfg.max_length
            
            # 在区间 [min_length, max_length] 内找断点
            best_breakpoint = None
            
            for bp in breakpoints:
                if range_start <= bp <= range_end:
                    best_breakpoint = bp
                    break
            
            # 区间内没找到断点，尝试弹性延伸
            if best_breakpoint is None and self.cfg.allow_exceed_max:
                for bp in breakpoints:
                    if range_end < bp <= segment_start + self.cfg.hard_max_limit:
                        best_breakpoint = bp
                        break
            
            # 超过熔断上限或找不到断点，强制截断
            if best_breakpoint is None:
                forced_end = min(segment_start + self.cfg.hard_max_limit, len(text))
                segment = text[segment_start:forced_end].rstrip()
                if segment:
                    segments.append(segment)
                segment_start = forced_end
                continue
            
            # 提取分段内容
            segment = text[segment_start:best_breakpoint]
            if not self.cfg.keep_symbol:
                # 不保留符号，去除尾部空白
                segment = segment.rstrip()
            
            if segment:
                segments.append(segment)
            
            segment_start = best_breakpoint
        
        # 短尾合并
        if self.cfg.merge_short_tail and len(segments) >= 2:
            last_segment = segments[-1]
            second_last = segments[-2]
            
            if len(last_segment) <= self.cfg.short_tail_threshold:
                # 合并到最后一段
                segments[-2] = second_last + last_segment
                segments.pop()
        
        return segments if segments else [text]

    def _save_segment_history(self, original_text: str, segments: List[str], replace_count: int, event: AstrMessageEvent):
        """
        保存分段历史（调试用）

        Args:
            original_text: 原始文本
            segments: 分段后的文本列表
            replace_count: 替换次数
            event: 消息事件
        """
        try:
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
        logger.info(f"[分段插件] 处理完成，替换 {replace_count} 处，分段 {len(segments)} 段")

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