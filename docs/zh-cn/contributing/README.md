# 参与贡献

在本地搭建构建环境、验证改动并快速熟悉 kara-templater 代码结构。修改库代码、文档或发布配置前，可以先从这里入手。

## 快速检查

先按[配置开发环境](setup.md)安装依赖和检查工具，然后在仓库根目录运行以下命令，确认代码风格检查、类型检查、核心测试和文档校验都能通过：

```sh
uv run ruff check .
uv run ty check
uv run python -m pytest
uv run python -m tools.check_scene_types
uv run python -m tools.check_docs
```

## 验证视觉改动

修改特效或渲染路径后，请导出一段有代表性的短歌词 Hook，并检查改动涉及的每个时间边界两侧的效果。例如，调整卡拉 OK 走字（扫色）后，要同时查看音符交接前后的画面。如果现有测试没有覆盖该边界，请补充一条聚焦的回归测试。测试范围选择和预览命令见[检查与文档验证](checks.md)。

## 贡献指南导览

| 目标 | 指南 |
| --- | --- |
| 安装 Python、C++、Rust 和字体等前置依赖 | [配置开发环境](setup.md) |
| 查找歌词、场景与导出器对应的模块 | [架构概览](architecture.md) |
| 运行检查套件、测试、API 参考生成与视觉预览 | [检查与文档验证](checks.md) |
| 编写双语文档、添加画廊示例并构建站点 | [编写与构建文档站点](documentation-site.md) |
| 构建分发包、运行隔离校验并发布版本 | [构建与验证发布包](releasing.md) |

## 下一步

- [配置开发环境](setup.md)
- [架构概览](architecture.md)
- [检查与文档验证](checks.md)
