# Custom Segment Reply (本地智能分段)

纯本地计算、零成本、极速响应的多维断句引擎。

---

## 功能列表

1. 按规则自动将长消息分段发送
2. 支持关键词排除（特定内容不分段）
3. 支持字符替换（如将表情替换为其他）
4. 支持 Markdown 格式移除
5. 保存分段内容到对话历史

---

## 核心原理

### 四维断句引擎 (Quad-Core Segment Engine)

不是简单的"按标点切割"，而是一套拟人化的判定程序：

- **区间探测**：优先在 [最小字数, 最大字数] 黄金区间内寻找断点，保证每一句话长短适中
- **优先等级锚定**：根据设定的符号优先级列表（如换行符 > 句号 > 逗号），优先在最强烈的意思停顿处断开
- **标点吸附**：支持灵活配置断句后是否保留原标点，满足不同人设定的文字习惯

### 超长降级保护

遇到没有标点符号的几百字纯英文/乱码怎么办？程序会死循环吗？

不存在的。系统内置了强大的降级保护机制：

- **弹性延伸** (`allow_exceed_max`)：当黄金区间内找不到标点时，程序会允许突破最大字数限制，继续向后寻找第一个出现的标点，保证句子完整不被生硬切断
- **绝对熔断** (`hard_max_limit`)：如果向后延伸到设定的"硬性熔断极限"（如 100 字）仍然没有标点，系统将无情介入，执行物理截断，彻底杜绝超长消息刷屏和内存溢出

### 短尾智能合并

**告别机器人说话大喘气！**
如果切割到最后，剩下的文本只有孤零零的几个字（例如："好的。"、"没问题~"），单独发出来不仅突兀，还会破坏对话节奏。
触发短尾合并后，系统会"撤回最后一刀"，将这极短的尾巴无缝缝合到上一句话中一并发出。

### 极致轻量架构

- **0 依赖**：无需安装 `aiohttp`，不发起任何网络请求
- **0 成本**：完全不消耗大模型 Token 额度
- **0 延迟**：内存级运算，即插即用，主打一个稳如泰山

---

## 安装与配置

1. 将本仓库下载后，把文件夹放入 `AstrBot/data/plugins/` 目录（请确保文件夹名为 `astrbot_plugin_custome_segment_reply`）
2. 重启 AstrBot
3. 在 AstrBot 的 WebUI 管理面板 -> 插件设置中，找到本插件即可进行**可视化配置**

### 配置示例

```json
{
  "min_length": 20,
  "max_length": 50,
  "allow_exceed_max": true,
  "hard_max_limit": 100,
  "merge_short_tail": true,
  "short_tail_threshold": 8,
  "split_symbols": ["\n\n", "\n", "。", "！", "？"],
  "keep_symbol": true,
  "exclude_keywords": ["模型列表", "帮助", "help", "命令列表", "菜单", "功能列表"],
  "enable_string_replace": true,
  "enable_markdown_replace": true,
  "string_replacements": [
    "😁=>🥺",
    "😂=>🤤"
  ],
  "markdown_replacements": [
    {"pattern": "\\*\\*([^*]+)\\*\\*", "replacement": "$1", "is_regex": true}
  ]
}
```

### 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `min_length` | int | 20 | 触发断句的下限，在此字数内尽量不断句 |
| `max_length` | int | 50 | 常规模断句上限，搜索断点的黄金区间 |
| `allow_exceed_max` | bool | true | 允许在没找到标点时突破上限往后找 |
| `hard_max_limit` | int | 100 | 绝对熔断长度，防止无限搜索 |
| `merge_short_tail` | bool | true | 开启短尾合并 |
| `short_tail_threshold` | int | 8 | 最后一段剩余字数少于等于此值时触发合并 |
| `split_symbols` | list | `["\n\n", "\n", "。", "！", "？"]` | 程序会优先搜索靠前的符号进行切割 |
| `keep_symbol` | bool | true | 开启则断句后保留该符号；关闭则断句后直接丢弃 |
| `exclude_keywords` | list | `["模型列表", "帮助", ...]` | 包含以下关键词时，将跳过整段处理 |
| `enable_string_replace` | bool | true | 启用字符串替换 |
| `enable_markdown_replace` | bool | true | 启用 Markdown 移除 |
| `string_replacements` | list | `["😁=>🥺", ...]` | 字符串替换规则列表，格式：`原字符=>替换后字符` |
| `markdown_replacements` | list | `[{"pattern": "...", ...}, ...]` | Markdown 替换规则，支持正则表达式 |

---

## 替换规则详解

### 字符串替换
格式：`原字符=>替换后字符`
```json
"string_replacements": [
  "😁=>🥺",
  "笑死=>哈哈",
  "[敏感词]=>***"
]
```

### Markdown 替换（正则表达式）
```json
"markdown_replacements": [
  {"pattern": "\\*\\*([^*]+)\\*\\*", "replacement": "$1", "is_regex": true},
  {"pattern": "`([^`]+)`", "replacement": "$1", "is_regex": true},
  {"pattern": "^#{1,6}\\s+", "replacement": "", "is_regex": true}
]
```

支持的 Markdown 格式清理：
- `**bold**` → `bold`
- `*italic*` → `italic`
- `` `code` `` → `code`
- 代码块整体移除包覆
- `# 标题` → `标题`
- `> 引用` → `引用`
- `- 列表项` → `列表项`
- `~~删除线~~` → `删除线`
