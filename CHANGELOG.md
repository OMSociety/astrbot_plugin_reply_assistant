# 更新日志

> 本项目仍处于活跃维护中。

---

## [1.1.0] - 2026-04-25

### 新增
- 重写 `_segment_text` 实现区间探测分段算法
- 实现弹性延伸（`allow_exceed_max`）、绝对熔断（`hard_max_limit`）、短尾合并（`merge_short_tail`）
- 保留字符串替换功能
- 保留 Markdown 清除功能，加粗和代码完全清除

### 修复
- 修复插件 ID 统一为 `astrbot_plugin_reply_assistant`
- 修复 `_conf_schema.json` 格式错误
- 移除冗余的 emoji/character_replace 和 history/debug 配置

### 文档
- 更新 README 删除营销话术，补充字符串替换说明
- 添加原项目引用
- 添加 Logo 来源致谢
