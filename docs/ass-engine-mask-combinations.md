# P3 遮罩与组变换组合核对

第九十五批核对固定组合及错误边界，结合五个 P3 案例的逐例验收，完成“案例与遮罩/组组合”要求。柔和扫色的多策略比较仍为独立未完成项。

| 组合 | 具体证据 | 范围 |
| --- | --- | --- |
| 父组非等比缩放、旋转、剪切与子旋转 | test_scene_affine 中直接标量变换与组合矩阵对照；文字/路径和局部矩形遮罩对照显式世界路径，RGBA 相同 | 仿射降为路径，保留实际遮罩位置；不是把子旋转直接加到父缩放上 |
| 共享局部遮罩与不同子对象坐标 | test_group_masks 独立构造父组世界多边形，分别应用于子对象；包括渐变材质 | 像素一致；共享遮罩按所属组变换，不使用各子对象的变换 |
| 嵌套遮罩与孔洞 | 矩形相交的手工边界/孔洞参考、两个非凸遮罩、正反向四种组合 | 直接矢量参考像素一致；矩形与矢量光栅差异在边界外 1 px 分开检查，内部满足集合运算 |
| 父组时钟、子寿命和复制 | 动态遮罩在组局部 0.637 秒切换，子对象晚出生，复制延迟 2 秒 | 原输出 1640 ms 开始、量化差 3 ms；复制的调用时钟相同且输出只平移时间 |
| 镜像、零面积与近奇异 | test_scene_affine 的反射、缩放跨零、近奇异；test_group_masks 的奇异局部遮罩及反向语义 | 无负缩放标签误用；几何可查询，零面积不产生填充，反向遮罩保留约定行为 |
| 预算与来源诊断 | 路径/遮罩预检在回调前执行；布尔工作预算按遮罩所属对象报告，动态回调异常保留来源 | 超预算拒绝，不自动减点、缩帧或丢弃遮罩 |

以上参考部分独立展开变换和集合边界，之后与实际共用路径序列化及 libass 光栅器；不能作为独立光栅器证明。动态复杂示例由实际导出 ASS 连播/跳转补充，不能用预览截图替代上述组合回归。

## 当前固定示例

| 示例 | 事件 / 峰值 / 字节 | 播放证据 |
| --- | --- | --- |
| [共享组遮罩](../examples/scene_group_masks.py) | 905 / 5 / 567637 | [报告](scene-group-masks-validation.json)，300 帧、6 次跳转 |
| [仿射组合](../examples/scene_affine.py) | 405 / 3 / 476600 | [报告](scene-affine-validation.json)，300 帧、6 次跳转 |
| [镜像与退化](../examples/scene_mirror.py) | 387 / 3 / 770236 | [报告](scene-mirror-validation.json)，300 帧、6 次跳转 |

全部重复生成一致、时间量化差 0，低于固定单例预算；报告包含字体、renderer、策略和运行成本。共享组遮罩当前预览已检查。

复验：

```sh
uv run python -m pytest -q tests/test_scene_affine.py tests/test_group_masks.py tests/test_path_boolean.py
uv run python -m tools.validate_scene_core --scene group-masks build/ass-engine/group-masks-final
uv run python -m tools.validate_scene_core --scene affine build/ass-engine/affine-final
uv run python -m tools.validate_scene_core --scene mirror build/ass-engine/mirror-final
uv run ruff check .
uv run ty check
```

44 项回归、Ruff、ty 通过。P3 的五个效果另见 [E03](e03-acceptance.md)、[E04](e04-acceptance.md)、[E05](e05-acceptance.md)、[E09](e09-acceptance.md)、[E11](e11-acceptance.md)。它们与本组合核对共同构成案例要求的证据；策略比较、其他播放器和发行不由此完成。
