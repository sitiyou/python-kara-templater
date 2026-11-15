# v0.1.0 Python 模板兼容

本次版本保留模板入口，不设弃用或移除日期。新旧前端的统一场景路径及弃用决定见 [迁移核对](track-scene-migration-audit.md)。

旧模板作为显式前端接入统一 Document → Scene → 标准 ASS 流程。解析 Document 不执行代码；调用 `apply_templates` 或 `Engine.to_scene` 才执行 ASS 内的 Python 模板。

```python
from kara_templater import Document, apply_templates

source = Document.load("input.ass")
result = apply_templates(source)
result.save("output.ass")
```

文件入口：

```sh
kara-templater input.ass output.ass --templates
kara-templater input.ass output.ass --templates --video-size 1920 1080
```

`--templates` 明确选择可信 Python 模板执行；它不能与 `--effect`、Track 光栅选项或颜色/脉冲等预设参数混用。`--video-size` 保留旧版宽高比校正，只用于此入口。CLI 和 Python 默认使用相同 owner `legacy-templates`；新效果 CLI 的默认 owner 仍为 `default`。旧版无选项命令现在需要补充 `--templates`，避免普通导入隐式执行代码。

## 与新对象组合

```python
from kara_templater import Engine, Lifetime, TextObject

scene = Engine().to_scene(source)
scene.add(TextObject(id="cue", text="3 2 1", lifetime=Lifetime(0, 1)))
result = scene.compile()
result.document.save("mixed.ass")
```

`to_scene` 完成模板执行，把生成的 ASS Dialogue 放入 NativeEvent，不强制反解为新文字/动画对象。它们与新对象共享来源、输出排序、预算和序列化。对象按加入顺序输出；同一对象的原生归属注释与事件保持相邻，ASS Layer 仍决定最终层次。

模板选中且确实生成输出的源行保留为 `Comment`，Effect 置为 `karaoke`；模板/code 行、未匹配事件、其他节与可保留的自定义字段仍存在。按旧版规则先清理 Effect 恰为 `fx` 的旧 Dialogue。新框架的 `karaoke:v1:` 和 `kara:scene:v1:` 归属记录不会再次被旧模板隐式处理。执行新旧前端时由调用者明确目标和先后；同一 Scene 的 owner 表示共同重建的一组结果。

原生事件保留原有 Effect（如 `fx`），因此使用紧邻的 Comment 保存归属；不要求播放器识别这段注释。相同 owner 重建会清理已有输出，直接 Document 重建、保存后解析重建和 CLI 重建均有回归测试。手动删除原生事件、只保留其归属注释，会破坏这对记录；共享编译器会对本 owner 的残缺标记给出诊断。

旧模板的 `$li`/`orgline.i` 等继续使用旧版事件编号。新输出报告中的 SourceRef 使用输入 Document 的 `record:<索引>`，effect 标明模板事件编号。模板异常保留 `Event N (template/code ...)` 上下文。调用者的输入 Document 不被修改。

## 兼容矩阵与证据

基准是仓库 git 标签 `v0.1.0`。该版本使用 Python，不包含 Lua 解释器；本兼容入口不宣称可以执行任意 Aegisub Lua 模板。

| 范围 | 保留行为 | 验证 |
| --- | --- | --- |
| 模板解析 | template/code、默认模式、once/line/pre-line/syl/furi、具名模板拼接 | 原始测试与差分 named_preline/code_loops_groups |
| 修饰符 | all、repeat/loop、notext、keeptags、noblank、char、multi、fx、fxgroup | 原始测试及 char_multi_inline_fx/keep_tags/no_match |
| 上下文 | 行/音节位置与时间变量、j/maxj、line/orgline/syl/basesyl、meta/styles、tenv | 原始测试及 variables/code_loops_groups |
| Python | code 执行顺序、`!…!` 表达式、引号内感叹号与 `!=`、math/random | 原始测试及 expression_quotes/seeded_random |
| 时间 helper | retime 的 line/preline/postline/syl/presyl/postsyl/start2syl/syl2end/abs/set/sylpct | 11 组独立差分；原始数值断言 |
| 其他 helper | relayer/restyle、maxloop/maxloops/loopctl、remember/recall/remember_if、作用域及装饰器 | 原始测试与 memory/loop_controls |
| 旧歌词布局 | k/K/kf/ko、内联 fx、# 连续高亮、注音及断开/回溢标记、逐字宽度、宽高比校正 | 原始拆词/布局测试与 ruby_continuation |
| 文档保留 | 未匹配事件、模板/code、字段顺序、自定义列、Fonts 等节、输入不变 | 原始测试与 `tests/test_legacy_scene.py` |
| 统一输出 | NativeEvent 来源、与新对象的顺序、零时长/负起点、预算、重复生成 | `tests/test_legacy_scene.py` 与实际混合示例 |
| 入口与类型 | 文件/直接 Document/CLI 一致、显式执行、公开参数和返回类型 | CLI 回归、`tests/typing/legacy.py`、错误类型反例 |

`tests/test_legacy_v010.py` 恢复该标签的 31 个测试，只调整格式、类型收窄和原始示例夹具位置。夹具为 `tests/fixtures/v010-karaoke.ass`，避免现有 `examples/karaoke.ass` 的后续修改影响历史基线。

```sh
uv run python -m pytest tests/test_legacy_v010.py tests/test_legacy_scene.py -q
uv run python -m tools.validate_legacy_templates /tmp/legacy-validation
uv run python -m tools.check_scene_types
```

差分工具在临时目录直接提取标签的 ass/layout/engine 源码，使用同一个当前 native metrics 扩展运行两个引擎。23 组输入在仅去除新增归属 Comment 后，完整 ASS 文本相同，见[报告](legacy-template-validation.json)。这是 Python 行为和序列化的差分；不等于重建了 v0.1.0 的历史字体环境或原生二进制。

## 时间、类型与预算边界

兼容模板、preprocess、split_karaoke 和 helper 的时间仍为毫秒；新场景动画使用秒。NativeEvent 保留旧模板可能产生的负时间、零时长或倒置区间，在 Document 序列化时沿用负时间钳制为零的规则；新 TextObject/PathObject 的 Lifetime 仍要求正显示区间。

`preprocess` 保留原地修改和事件身份，为普通 Line 附加 LegacyLine 类型的历史布局视图。LegacySyllable 保留动态字典扩展，并对历史字段给出明确类型；旧代码自定义的字段仍为 object。场景入口不会把这些动态字典作为新动画 API。

`Engine(max_iterations=..., max_output_lines=..., budget=SceneBudget(...))` 保留旧循环/输出数量限制，并在标准 ASS 编译阶段执行共享预算。任意 Python 代码不能在执行前完整预测输出，因此旧执行阶段由 max_output_lines 限制，新场景编译再做原生事件预检。默认场景预算可能比旧版 100,000 行上限更严格；原生归属注释也计入记录和字节预算。需要更大输出时显式指定预算。旧模板 random 模块保留原语义；只有显式 seed 的模板才保证随机结果可重建。

固定混合示例为 [scene_legacy.py](../examples/scene_legacy.py)：旧代码、正文/注音模板与新场景淡入淡出说明文字共享一次编译。[实际预览](images/scene-legacy.png)和[报告](scene-legacy-validation.json)记录 60 个事件、峰值 8、25,963 字节，以及连续 300 帧和重新加载跳转一致性。
