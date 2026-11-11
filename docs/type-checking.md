# 类型与质量检查

这是供 Python 代码直接使用的库。公开接口应提供可补全、可推断的参数和返回值，
不能只靠给返回值写一个类型来掩盖实现中的 `Unknown` 或 `Any`。

## 使用与检查

```sh
# 需要支持 dependency groups 的 pip；只安装检查工具，不编译原生扩展。
python -m pip install --upgrade pip
python -m pip install --group checks
ruff check .
ty check

# 已完成项目本身的安装/原生扩展构建后运行：
python -m pytest -q
```

`checks` 组固定 Ruff 0.17.4、ty 0.0.100。升级时需要检查新增/变化的诊断规则，
并运行类型契约测试。GitHub Actions 的 `quality` 作业使用相同配置，构建作业
依赖它通过。原有 wheel 测试仍负责各目标环境的运行时验证。

库随包发布 `py.typed` 和 `_metrics.pyi`，让安装后的库与源码目录拥有相同的
类型入口。原生扩展的声明对应 `native/metrics.cpp` 的实际参数和返回结构。

## 公开接口的类型契约

```python
from kara_templater import Body, Halo, Ruby

bodies = self.query(Body)                   # tuple[Body, ...]
ruby = self.query_one(Ruby)                 # Ruby
light = self.query_one("#light", Halo)      # Halo，运行时也验证类型
component = self.query_one(".accent")       # Component
selected = self.characters[1:3]             # TargetSelection
selected.style.sung.fill = "#67e5ff"         # 写入颜色字符串，读取为 Color/StyleKeyword
selected.on_singing(scale=lambda p: 1 + p)   # p: float，返回值必须为 float
```

类查询包含子类，并保留查询类的静态类型；字符串选择器本身不能证明组件类型。
`query_one` 始终要求恰好一个匹配；预期类型与实际类型不同会抛出 `TypeError`。

组件构造、样式、动画、时间表达式、来源集合、文档读写和渲染入口都有明确类型。
`EffectInput` 描述效果类、带 `build` 的对象、配方函数及按样式分派的映射。
`PropertyValue` 描述常量、二元过渡、关键帧、标量回调和 `Contextual`。
动画方法明确列出 `scale`、`opacity`、`offset_x`、`offset_y`；拼错参数名既会被
静态检查发现，也会在运行时作为未知关键字报 `TypeError`。

`Record` 仍允许任意 ASS 元数据键，但动态访问返回 `object`，需要使用者按实际
内容收窄；标准分辨率字段有明确类型。它不会把动态值当作任意目标类型使用。

防回归分成三层：

- Ruff 要求库内公开函数、特殊方法和类/静态方法声明返回类型，禁止参数里的显式 `Any`。
- `tests/test_typing.py` 审计顶层导出的函数、类自身定义的方法与构造函数的参数和返回注解，
  同时递归检查注解和类型别名中是否含有 `Any`。
- `tests/typing/` 使用 `assert_type` 验证真实用户调用链，并用精确的预期诊断验证非法调用。
  预期诊断消失时，`unused-ignore-comment` 会让检查失败，防止接口退化为动态类型后反而“通过”。

普通测试函数、示例和工具脚本不强制所有返回注解，但仍参与完整的错误检查和类型检查。
未全局启用 `ANN001/ANN002/ANN003/ANN202`：它们会同时要求每个内部辅助函数都标注；
公开入口的参数完整性由上述导出审计约束。后续可以逐模块扩展内部注解要求，不用
`Any`、整文件忽略或诊断基线来消除待补的注解。

## Ruff 规则选择

配置明确列出规则，不使用 `ALL`。Ruff 官方建议按组增加规则，并提醒 `ALL` 会随
版本升级自动启用新规则。[官方说明](https://docs.astral.sh/ruff/linter/#rule-selection)

| 规则 | 用途 |
| --- | --- |
| `E4/E7/E9`、`F` | 导入位置、语法、未定义名称、未使用导入等基础问题 |
| `I`、`UP` | 导入排序与 Python 3.12 可用的现代语法 |
| `B` | Bugbear 常见错误；例如 `zip` 必须明确长度关系 |
| `SIM`、`C4`、`PIE` | 可简化控制流、冗余推导式和不必要结构 |
| `PGH`、`RUF100` | 避免宽泛忽略，清理失效 `noqa` |
| `RUF013` | 可空参数必须显式写 `None` 联合类型 |
| `ANN201/204/205/206`、`ANN401` | 公开返回类型及禁止显式 `Any` 参数 |

`E731` 和 `E741` 不启用：本库有大量命名 lambda 回调、坐标和图层短变量，
这两项风格限制对这些代码帮助有限。格式继续遵循现有 Black 约定，不要求
`ALL` 中相互冲突的文档风格，也不按函数参数数量限制可定制效果。

## ty 的额外严格检查

保留 ty 默认错误检查，并明确打开以下额外规则；warning 也会使命令失败。

| 规则 | 用途 |
| --- | --- |
| `unsound-return-statement` | 禁止返回 `Unknown`/`Any` 来兑现一个具体返回类型 |
| `unsound-assignment`、`unsound-yield` | 防止动态类型经赋值和生成器进入具体类型契约 |
| `missing-type-argument` | 禁止裸 `list`、`dict`、`tuple` 等隐式动态容器 |
| `possibly-missing-attribute/import` | 检查条件定义的属性和导入 |
| `possibly-unresolved-reference` | 检查分支或循环之后可能未定义的变量 |
| `division-by-zero`、`redundant-cast` | 常量除零和已经不需要的类型转换 |
| `blanket-ignore-comment`、`unused-ignore-comment`、`unused-type-ignore-comment` | 每条忽略必须有具体原因和有效诊断编号 |

默认类型检查只要求返回值可以赋给声明类型；ty 的 soundness 规则进一步阻止
`Any`/`Unknown` 利用这种兼容性穿过边界，这正是本库需要的额外严格度。
这些规则默认关闭，官方将它们定位为需要更高可靠性的进阶检查。
[ty 官方规则说明](https://docs.astral.sh/ty/reference/rules/#unsound-return-statement)

不启用 `redundant-condition-strict`：库必须对未标注的 Python 调用者进行运行时
校验，不能因为类型注解声称参数合法，就删除 `isinstance` 等检查。不强制
`missing-override-decorator`，避免给每个声明式 `compose/configure` 增加装饰器要求；
开发者仍可使用 `typing.override`。不设置 `all = "error"`，保持升级时的规则范围可审查。
[规则等级与配置](https://docs.astral.sh/ty/rules/)
