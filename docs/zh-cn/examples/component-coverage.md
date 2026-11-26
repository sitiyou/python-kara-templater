# 组件库与可编辑组件

此表以组件库的 124 张卡片为索引。多个对比示例可能对应同一个参数。组件声明来自 `effect_components()`，以脚本分辨率计算几何默认值。

启用实时绑定的实色扫描线可以直接修改 shader 参数。其他表列组件通过场景构建更新。表中需要源码的示例注明了所需的对象、路径、回调或渲染后端。

## 内置预设

| 类别 | 卡片与组件 ID |
| --- | --- |
| 入场 (20) | `entry-none`, `entry-fade`, `entry-slide-in`, `entry-rise`, `entry-char-fade`, `entry-char-drip`, `entry-spin-flip`, `entry-utopia`, `entry-tilt-pop`, `entry-tracking-in`, `entry-wave-in`, `entry-stretch-in`, `entry-glow-in`, `entry-assemble-in`, `entry-sparkle`, `entry-ripple`, `entry-note`, `entry-petal`, `entry-snow`, `entry-snow-solid` |
| 退场 (19) | `exit-none`, `exit-fade`, `exit-slide-out`, `exit-rise`, `exit-char-fade`, `exit-char-drip`, `exit-spin-flip`, `exit-utopia`, `exit-scatter-out`, `exit-converge-out`, `exit-stretch-out`, `exit-glow-out`, `exit-dissolve-out`, `exit-sparkle`, `exit-ripple`, `exit-note`, `exit-petal`, `exit-snow`, `exit-snow-solid` |
| 走字与高亮 (7) | `highlight-none`, `highlight-no-wipe`, `highlight-utopia`, `highlight-scanline`, `highlight-utopia-scanline`, `highlight-zoom-pulse`, `highlight-zoom-pulse-scanline` |
| 节拍装饰 (8) | `decoration-none`, `decoration-twinkle`, `decoration-twinkle-classic`, `decoration-note`, `decoration-ripple`, `decoration-petal`, `decoration-snow`, `decoration-snow-solid` |

## 独立示例

| 卡片 ID | 组件、参数或要求 |
| --- | --- |
| `default-recipe` | `entry-fade`, `exit-fade`, `highlight-utopia`, `decoration-none` |
| `duotone` | `lyric-colors.dual_outline` |
| `stroke-flash` | `stroke-flash` |
| `soft-front` | `soft-front` |
| `bars-cue` | `bars-cue` |
| `volume-cue` | `volume-cue` |
| `signal-cue` | `signal-cue` |
| `text-cue` | `text-cue` |
| `fade-in` | `fade-in` |
| `fade-out` | `fade-out` |
| `slide` | `slide` |
| `jump` | `jump` |
| `scale-pulse` | `scale-pulse` |
| `curve-in` | 此卡片沿自定曲线采样缓动。 |
| `drift-out` | `drift-out` |
| `scatter-out` | 此卡片为各字形采样离场路径。内置退场提供径向散开和粒子消散。 |
| `tween` | `tween-scale.scale` 可设终点缩放。示例还指定了终点位置和两段式曲线。 |
| `move-along` | 需指定运动路径及作用对象。 |
| `lyric-highlights` | `lyric-colors` |
| `karaoke-theme` | `lyric-colors` |
| `lyric-gradient` | `lyric-gradient` |
| `linear-gradient` | `lyric-gradient.axis` |
| `glow` | `glow` |
| `secondary-outline` | `outline` |
| `extrusion` | `extrusion` |
| `material-effect` | 需编写 WGSL 并绑定需公开的可调参数。 |
| `shader-paint` | 需编写 GLSL 和相应参数。 |
| `sparkle` | `sparkle` |
| `petal` | `petal` |
| `ribbon` | 需绘制缎带路径并定义定时发射工厂。 |
| `lyric-echo` | `echo` |
| `echoes` | 需提供要复制的对象和时钟。 |
| `ruby` | `ruby-layout` |
| `karaoke-rows` | `karaoke-rows` |
| `vector-guide` | 需给出字符与矢量路径的对应关系。 |
| `rectangle-clip` | 此例在场景坐标中定义裁剪与关键帧。 |
| `trail-path` | 需绘制路径并指定尾迹长度。 |
| `write-path` | 需定义图形的笔画与笔顺。 |
| `morph-path` | 需提供可插值的起止路径。 |
| `timeline` | 需编排时间锚点和动画区间。 |
| `shader-motion` | 需成对编写 shader 和 Python 求值函数。 |
| `transform` | 此例使用自定义变换回调。 |
| `state-function` | 需编写状态回调，并声明它能修改哪些属性。 |
| `follow-object` | 需指定场景中的参照对象。 |
| `object-group` | 需编排场景分组及其子对象。 |
| `rectangle-function` | 此例用自定义函数控制移动矩形。 |
| `path-function` | 此例用自定义函数生成变化的路径。 |
| `vector-clip` | 此例使用标准 ASS 的矢量裁剪。 |
| `type-family` | `typography.fontname` |
| `type-size` | `typography.fontsize` |
| `type-bold` | `typography.bold` |
| `type-italic` | `typography.italic` |
| `type-spacing` | `typography.spacing` |
| `type-scale` | `typography.scale_x`, `typography.scale_y` |
| `type-border` | `typography.outline` |
| `type-blur` | `glyph-blur.blur` |
| `type-shadow` | `offset-shadow.x`, `offset-shadow.y` |
| `sweep-color` | `highlight-scanline.scanline_color`（可实时绑定） |
| `sweep-brighten` | `band-brighten` |
| `sweep-follow-before` | `band-follow-before` |
| `sweep-follow-after` | `band-follow-after` |
| `sweep-width` | `highlight-scanline.scanline_width`（可实时绑定） |
| `sweep-softness` | `highlight-scanline.scanline_softness`（可实时绑定） |
| `sweep-strength` | `highlight-scanline.scanline_strength`（可实时绑定） |
| `sweep-gradient` | `band-gradient` |
| `sweep-feather` | `soft-front.hook_feather` |
| `sweep-front-tint` | `soft-front.front_color` |
| `sweep-angle` | `highlight-scanline.sweep_angle` |
| `sweep-reverse` | `highlight-scanline.reverse_wipe` |
| `sweep-ruby` | `highlight-scanline.ruby_scanline` |
