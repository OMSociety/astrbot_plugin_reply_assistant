# 分段与文本替换

[![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)](https://github.com/OMSociety/astrbot_plugin_reply_assistant)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

基于规则引擎的智能消息分段插件，支持字符串替换、Markdown 清除、平台打字状态模拟。

> 本项目由AI编写，部分源码基于 [astrbot_plugin_custome_segment_reply](https://github.com/LinJohn8/astrbot_plugin_custome_segment_reply) 。
> 
> 插件 Logo 来源于 Pixiv Pid: [115400125](https://www.pixiv.net/artworks/115400125)

[快速开始](#-快速开始) • [分段算法](#-分段算法) • [配置项](#-配置项说明) • [更新日志](CHANGELOG.md)

---

## 📖 功能概览

### 核心能力
- **智能分段** — 区间探测 + 弹性延伸 + 绝对熔断三级策略，长文本按标点优先级自动拆分
- **字符串替换** — 自定义文本替换规则，支持表情映射、敏感词过滤等场景
- **Markdown 清除** — 自动剥离加粗、代码块、标题等格式标记，保留正文内容
- **排除规则** — 关键词 + 正则双通道，帮助列表、菜单等特定消息免处理
- **短尾合并** — 最后一段过短时自动合并到前一段，避免碎片化消息
- **多平台打字状态** — 支持 QQ(aiocqhttp)、Telegram、Discord 等平台的「正在输入」状态显示，可配置开关

### 设计理念
零外部依赖，纯本地规则引擎。不调 LLM、不走网络，稳定可靠零成本。

---

## 🚀 快速开始

### 安装

**方式一：插件市场**
- AstrBot WebUI → 插件市场 → 搜索 `astrbot_plugin_reply_assistant`

**方式二：GitHub 仓库**
- AstrBot WebUI → 插件管理 → ＋ 安装
- 粘贴仓库地址：`https://github.com/OMSociety/astrbot_plugin_reply_assistant`

### 依赖
本插件无外部依赖，开箱即用。

---

## 🧠 分段算法

采用区间探测分段策略：

1. **区间探测** — 优先在 `[min_length, max_length]` 区间内寻找断点
2. **弹性延伸** — `allow_exceed_max=true` 时，向后扩展找下一个断点
3. **绝对熔断** — 超过 `hard_max_limit` 则强制截断
4. **短尾合并** — 最后一段过短时合并到前一段

---

## ⚙️ 配置项说明

### 分段配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `min_length` | int | 20 | 触发分段的最小字数 |
| `max_length` | int | 50 | 单段最大字数 |
| `allow_exceed_max` | bool | true | 启用弹性延伸 |
| `hard_max_limit` | int | 100 | 绝对熔断字数上限 |
| `merge_short_tail` | bool | true | 启用短尾合并 |
| `short_tail_threshold` | int | 8 | 短尾合并阈值 |
| `split_symbols` | list | 见下方 | 断句符号列表（按优先级） |
| `keep_symbol` | bool | false | 保留断点符号 |

`split_symbols` 默认值：`["\n\n", "\n", "。", "！", "？"]`

### 打字状态配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_typing_indicator` | bool | true | 发送分段时显示「正在输入」状态 |

### 排除配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `exclude_keywords` | list | 见下方 | 排除关键词列表 |
| `exclude_patterns` | list | `[]` | 排除正则表达式列表 |

`exclude_keywords` 默认值：`["模型列表", "帮助", "help", "命令列表", "菜单", "功能列表"]`

### 字符串替换配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_string_replace` | bool | false | 启用字符串替换 |
| `string_replacements` | list | `["小笨蛋=>小可爱"]` | 替换规则列表 |

格式：`原字符=>替换后字符`

示例：
```json
"string_replacements": [
  "😁=>🤪",
  "笑死=>哈哈",
  "[敏感词]=>***"
]
```

### Markdown 清除配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_markdown_replace` | bool | false | 启用 Markdown 清除 |
| `markdown_replacements` | list | 见 schema | Markdown 清除规则列表 |

默认清除格式标记，但保留正文内容：
- `**加粗**` → `加粗`
- `` `代码` `` → `代码`
- `# 标题` → `标题`
- `> 引用` → `引用`
- `~~删除线~~` → `删除线`
- `*斜体*` / `_斜体_` → `斜体`

**保留的格式**（不处理）：链接 `[文字](url)`、图片 `![alt](url)`、列表 `- item`

---

## 📝 更新日志

> 📋 **[查看完整更新日志 →](CHANGELOG.md)**

---

## 🤝 贡献与反馈

如遇问题请在 [GitHub Issues](https://github.com/OMSociety/astrbot_plugin_reply_assistant/issues) 提交，欢迎 Pull Request！

---

## 📜 许可证

本项目采用 **MIT License** 开源协议。

---

## 👤 作者

**Slandre & Flandre** — [@OMSociety](https://github.com/OMSociety)
