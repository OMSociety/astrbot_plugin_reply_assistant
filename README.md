# 分段与文本替换插件

> 本项目基于 [astrbot_plugin_custome_segment_reply](https://github.com/LinJohn8/astrbot_plugin_custome_segment_reply) 重构。

---

## 功能列表

1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符串替换（如将表情替换为其他）
4. 支持 Markdown 格式清除

---

## 安装

1. 将插件文件夹放入 `AstrBot/data/plugins/` 目录
2. 重启 AstrBot
3. 在 WebUI 管理面板 -> 插件设置中配置

---

## 分段算法

采用区间探测分段策略：

1. **区间探测**：优先在 `[min_length, max_length]` 区间内寻找断点
2. **弹性延伸**：`allow_exceed_max=true` 时，向后扩展找下一个断点
3. **绝对熔断**：超过 `hard_max_limit` 则强制截断
4. **短尾合并**：最后一段过短时合并到前一段

---

## 配置项说明

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

### 排除配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `exclude_keywords` | list | 见下方 | 排除关键词列表 |
| `exclude_patterns` | list | `[]` | 排除正则表达式列表 |

`exclude_keywords` 默认值：`["模型列表", "帮助", "help", "命令列表", "菜单", "功能列表"]`

### 字符串替换配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_string_replace` | bool | true | 启用字符串替换 |
| `string_replacements` | list | `["😁=>🤪", "😂=>🤭"]` | 替换规则列表 |

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
| `enable_markdown_replace` | bool | true | 启用 Markdown 清除 |
| `markdown_replacements` | list | 见下方 | Markdown 清除规则列表 |

默认清除格式标记，但保留正文内容：
- `**加粗**` → 变成 `加粗`
- `` `代码` `` → 变成 `代码`
- ```` ```代码块``` ```` → 去掉反引号仍保留代码内容
- `# 标题` → 去掉标题 `#` 符号
- `> 引用` → 去掉引用前导符
- `~~删除线~~` → 变成 `删除线`
- `*斜体*` / `_斜体_` → 去掉斜体标记后保留 `斜体`

**保留的格式**（不处理）：
- 链接 `[文字](url)` - 保持原样
- 图片 `![alt](url)` - 保持原样
- 列表 `- item` - 保持原样

---

## 配置示例

```json
{
  "min_length": 20,
  "max_length": 50,
  "allow_exceed_max": true,
  "hard_max_limit": 100,
  "merge_short_tail": true,
  "short_tail_threshold": 8,
  "split_symbols": ["\n\n", "\n", "。", "！", "？"],
  "keep_symbol": false,
  "exclude_keywords": ["模型列表", "帮助", "help", "命令列表", "菜单", "功能列表"],
  "enable_string_replace": true,
  "string_replacements": [
    "😁=>🤪",
    "😂=>🤤"
  ],
  "enable_markdown_replace": true,
  "markdown_replacements": [
    {"pattern": "\\*\\*([^*]+)\\*\\*", "replacement": "\\1", "is_regex": true},
    {"pattern": "`([^`]+)`", "replacement": "\1", "is_regex": true}
  ]
}
```