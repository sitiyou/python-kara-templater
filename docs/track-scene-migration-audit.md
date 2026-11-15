# Track 与旧模板的场景迁移核对

当前统一流程是 Document → 前端准备 → 场景对象或原生事件 → 标准 ASS。文件入口先解析 Document；解析本身不执行模板。旧入口继续保留，新作者可以从可编辑对象开始，不需要先生成 ASS 再反解。

## 入口选择

| 作者需要 | 公共入口 | 共享实现与输出 |
| --- | --- | --- |
| 维持现有 Effect/Track 输出并添加装饰 | `prepare_karaoke` | `_prepare_karaoke` 完成绑定与降级，NativeEvent 进入 Scene；回调在准备阶段运行 |
| 修改歌词对象、组变换、引用与动画 | `prepare_track_scene` | 同一准备阶段消费 `BoundTrack.prepare`，`track_objects` 生成普通 ObjectGroup/TextObject；回调延迟到 Scene 编译 |
| 编辑材质组件、着色后模糊、合成后透明度 | `prepare_track_coverage` | 同一准备阶段加 `track_coverage` 适配，返回普通组和显式材质绑定；`compile_coverage` 输出像素矩形 ASS |
| 执行 v0.1.0 Python 模板 | `apply_templates` / `Engine.to_scene` | 模板事件转换成 NativeEvent，共享 Scene 的来源、排序、预算与序列化 |

`render_karaoke` 仍是现有配置的一步出口。可编辑入口的采样由 SceneBudget 控制；Track.sampling 继续属于旧降级出口，不能悄悄改变新场景帧网格。覆盖率出口仍需显式 RasterSettings 与模糊/描边上界。所有出口均输出标准 ASS，不输出视频或要求播放器识别自定义指令。

## 常用配置覆盖

| 配置或行为 | 实现与直接证据 |
| --- | --- |
| 正文/注音、样式、时间与来源 | `PreparedTrack` 保存目标、布局、轨道及绑定；`test_preparation_keeps_text_ruby_paints_clocks_and_sources` 核对准备结果 |
| TrackGroup 多行分配 | 共用 `_prepare_karaoke` 布局；`test_editable_trackgroup_allocates_rows_and_restores_unselected_sources` 检查行距、层次与还原 |
| 缩放、位移、透明度及 pivot | `_track_scene._text_object` 复用 `sample_hierarchy`；准备测试核对 pivot、描边随缩放及实际 libass 像素 |
| 填充、描边宽度、动态辉光 | 共用材质绑定与 `_patch`；准备测试检查颜色/宽度，覆盖率测试比较动态辉光及嵌套 alpha |
| 硬边扫色和 release | 共用 `_compile_targets` 分区；转换为矩形遮罩与曝光寿命组；静态及运动夹具在声明采样中心对照原生输出 |
| 合成前着色和整词覆盖率 | `_track_coverage` 映射 components、partitions、glows、scope_opacities；`test_track_coverage.py` 与旧栅格参考比较，包括视口外扩展 |
| 作者编辑与新装饰 | 覆盖率前端测试直接修改根组平移并添加 PathObject，检查实际 ASS 像素；固定示例见下表 |
| 保存后重建、选择变化、入口切换 | Scene 与 coverage 前端测试检查 owner 清理、来源还原、其他 owner 保留及输入不变 |
| 预算和回调时机 | Scene 编译预检前不调用动态属性；对象数量与实际辉光边界均有失败测试，保留诊断 |

以上使用已有准备、排版、属性、材质和输出核心。没有额外实现一套歌词排版或另一个动画求值器。

## 保留的语义边界

- `prepare_track_scene` 使用每绘制层 alpha 和硬裁剪。Scene 的采样保持与旧原生连续插值不同；像素比较限定在声明采样中心。
- 可编辑 Track 当前明确拒绝样式下划线、删除线、Angle 和非普通 BorderStyle。需要原有表现时使用 `prepare_karaoke`；不能静默丢弃这些属性。
- 覆盖率 Track 前沿仅支持正向轴对齐等比变换，不把旋转/剪切前沿猜成二维材质分区。复制或重命名对象后需同时重定向材质身份及 scope owner。
- 栅格是显式昂贵出口；预算超限报错，不自动改用另一种透明度、模糊语义或降低采样质量。
- 旧独立 Halo、逐字 on_highlight 和 HighlightTrack 仍走 Effect/recipe 兼容入口；普通 Track 配置不冒充这些旧接口的同义替代。新 Scene 的路径、粒子和对象引用可以独立组合。

## 固定示例与验证

| 示例 | 用途 |
| --- | --- |
| [scene_tracks.py](../examples/scene_tracks.py) | 已降级 Track 与 Scene 装饰组合 |
| [scene_editable_tracks.py](../examples/scene_editable_tracks.py) | Track 转为可编辑歌词组 |
| [scene_coverage_tracks.py](../examples/scene_coverage_tracks.py) | 显式覆盖率材质与标准 ASS 输出 |
| [scene_legacy.py](../examples/scene_legacy.py) | 旧模板与新对象共同编译 |

第九十八批重新执行以下验证；完整结果记入[进度](ass-animation-engine-progress.md)：

```sh
uv run python -m pytest tests/test_track_scene.py tests/test_track_preparation.py tests/test_track_coverage.py tests/test_track_coverage_frontend.py tests/test_legacy_v010.py tests/test_legacy_scene.py -q
uv run python -m tools.validate_legacy_templates build/ass-engine/legacy-migration-audit
```

[当前差分报告](legacy-template-migration-validation.json)从 git 标签提取旧版 Python 实现，23 组完整 ASS 在去除新增归属注释后相同。两边共享当前 native 扩展，因此这是旧 Python 模板语义与序列化证据，不代表历史字体/播放器环境。逐功能兼容矩阵见 [legacy-templates.md](legacy-templates.md)。

## 弃用决定

本次版本保留 `Effect`、recipe、Track、`apply_templates` 和 `Engine.to_scene`，不增加弃用警告，不设移除版本或日期。它们承载的既有能力及用户兼容要求仍有效。新功能优先通过 Document/Scene 与公共动画、几何、材质接口提供；后续如需移除旧入口，须另行给出完整替代与版本迁移决定。

旧 CLI 无选项执行模板改为显式 `--templates` 是已记录的入口变化，不能称作命令行逐字兼容；文件 → Document → 模板 → Scene → ASS 的功能保留。毫秒制旧 helper 与秒制 Scene 的边界也继续保留，不自动重解释既有数值。
