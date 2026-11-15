# E10 固定形状插值验收

第八十七批：scene_morph.py 达到案例卡的 **libass 首版目标**，涵盖圆环到带孔方形、字形 B 到显式仿射目标的对应轮廓插值。没有跨拓扑自动匹配。

| 要求 | 证据 | 结果 |
| --- | --- | --- |
| 圆环、孔洞及对应顶点插值 | [几何参考](morph-validation.json)独立解析圆/方形顶点及 smoothstep | 175 时刻覆盖全部有内容状态，1 px 容差；填洞反例被检出，原始覆盖率差最大 54/255 |
| 字形 B 插值 | 同报告对原生文字覆盖率施加独立逆仿射；另用原生文字 scale/shear 参考验证颜色工具的字形 | 两种参考各 175 时刻满足 1 px；重建覆盖率差分别最大 87/255、109/255，单列为边缘差 |
| 时间与连续误差 | 153 静态区间首/中/末位图一致，量化差 0；20 ms 中点保持 | 固定 smoothstep 的控制点位移界：圆环 0.207107 px，字形 0.347224 px；不含字体/光栅近似和寿命跳变 |
| 四背景颜色 | [颜色报告](morph-colors-validation.json)：解析青色圆环及原生粉色 B 与实际 FFmpeg 比较 | 26 时刻 × 4 背景，共 3352316 个共同不透明内部像素差 0；整帧最大差 100/255 单列 |
| 播放和跳转 | [四背景报告](engine-backgrounds-morph-validation.json)每背景 600 帧连续/乱序；[单例报告](scene-morph-validation.json)300 帧与 6 次独立跳转 | 全部一致，重复生成一致，5000 ms 精确结束 |
| 成本与整曲 | 304 事件、峰值 2、647447 字节 | 低于预设 25000 / 1000 / 10 MiB；与整曲 E10 解码 UTF-8 BOM 后全文相同，耗时见单例报告 |
| 不匹配及预算诊断 | tests/test_path_geometry.py 核对轮廓数量、绕向、控制点对应及点数预算 | 相关几何与文件往返 28 项回归通过 |

[实际/参考/8 倍差图](images/morph-colors.png)已检查。颜色参考使用共享字体/光栅器，独立构造圆环和字形变换；共同内部的颜色结论不代表边缘像素一致。孔洞几何和对应关系另由几何参考及拓扑失败用例验证。

重现：

```sh
uv run python -m tools.validate_morph build/ass-engine/morph-all-states
uv run python -m tools.validate_cue_colors --case E10 build/ass-engine/morph-colors
uv run python -m tools.validate_engine_backgrounds --case E10 build/ass-engine/morph-final-backgrounds
uv run python -m tools.validate_scene_core --scene morph build/ass-engine/morph-final
```

Ruff、ty 和资产检查通过。P4 的 E08、其他阶段及发行仍待完成。
