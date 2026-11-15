# E12 固定导唱案例验收

第七十三批结论：E12 固定案例达到案例卡约定的 **libass 首版目标**。这不代表任意自定义导唱回调、所有播放器或 P2 整个阶段已验收。主例为 scene_lyric_cues.py；自定义矢量和歌词锚点跟随由 scene_cues.py、scene_cue_follow.py 补充。

| 要求 | 当前证据 | 结果与范围 |
| --- | --- | --- |
| 行内与独立、文本与矢量、可自定义内容 | 主例行内条形/数字和独立 READY/SET/GO；sparkle 工厂直接返回 PathObject；cue-follow 使用普通 FollowObject | 满足。无需播放器扩展标签；用户工厂可继续使用普通对象/动画 |
| 占位、释放、不改唱词时间与注音归属 | test_scene_text、test_lyric_cues；cues-validation.json 的独立标量布局、两次释放和组移动隔离 | 满足。几何覆盖 29 时刻，5 px 漂移反例检出 |
| 几何误差不超过 1 px | [布局报告](cues-validation.json)的填充及描边外包络；自定义图形另有 [218 项参考](custom-cue-validation.json) | 主例通过。最大填充/外包络覆盖率差 34/255、69/255 单独报告，符合案例卡“栅格抗锯齿边缘另报”，不称覆盖率像素一致 |
| 内部颜色误差不超过 2/255 | [颜色报告](cue-colors-validation.json)：四背景 68 帧、473,688 个共同不透明内部像素，包含青色导唱、白色歌词/注音、黑色描边 | 最大 RGB 差 0。共同内部用于颜色，轮廓缺失由独立几何检查约束；整帧边缘等差异最大 69/255 另报 |
| 时间量化不超过 10 ms | 输出静态标签白名单、全部事件区间、区间首/中/末位图一致；最大边界误差 1/300 秒 | 满足。0–6 秒共有 9 个区间，参考时刻覆盖每个区间。每个事件内部无 t/move/淡入淡出/卡拉 OK 标签，动态标签反例拒绝；不会把这个有限状态结论套用到任意回调 |
| 四背景连续与乱序一致 | [当前四背景报告](engine-backgrounds-cues-validation.json)，每背景 600 个厘秒网格时刻，连续和乱序各一次 | 全部一致，记录实际 libass、字体及背景。输出只依赖标准 ASS 和固定字体 |
| 事件、体积、峰值预算与重复生成 | [当前导出报告](scene-lyric-cues-validation.json)：57 事件、23 峰值、25,861 字节；重复生成一致 | 低于 25,000 / 1,000 / 10 MiB；300 帧连播和 11 次独立跳转一致 |
| 源文档与标记消费 | 文件/直接 Document 等价回归、owner 再生成、源 Comment 保留；生成 Dialogue 不含 cue/ruby 标记 | 满足固定输入协议；旧模板兼容另按 v0.1.0 矩阵验收 |

当前独立验证 ASS 与 whole-song-sakura-front/reference-E12.ass 的文本完全一致。原始 SHA-256 差异仅来自文件是否含 UTF-8 BOM，核对时使用 utf-8-sig 解码，不忽略任何其他字符；不将不同编码包装误报为动画变化。

## 重现

```sh
uv run python -m tools.validate_cues build/ass-engine/cues-time
uv run python -m tools.validate_cue_colors build/ass-engine/cue-colors
uv run python -m tools.validate_engine_backgrounds --case E12 build/ass-engine/cues-final-backgrounds
uv run python -m tools.validate_scene_core --scene lyric-cues build/ass-engine/cues-final
```

其他播放器、Windows 字体提供器和最终发行重建仍是 P5 未完成项。原生 Tween 可选降级不影响此案例的默认输出。未来修改主例内容、字体或编译策略后需要重新核对相应报告。
