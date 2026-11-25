import {defineConfig} from "astro/config";
import starlight from "@astrojs/starlight";

export default defineConfig({
  output: "static",
  site: process.env.DOCS_SITE || "https://sitiyou.github.io",
  base: process.env.DOCS_BASE || "/",
  publicDir: "../build/docs-site/public",
  outDir: "../build/docs-site/dist",
  integrations: [
    starlight({
      title: "kara-templater",
      favicon: "/favicon.png",
      logo: {src: "./favicon.png"},
      disable404Route: true,
      defaultLocale: "root",
      locales: {
        root: {label: "English", lang: "en"},
        "zh-cn": {label: "简体中文", lang: "zh-CN"},
      },
      components: {
        ThemeProvider: "./src/components/ThemeProvider.astro",
        ThemeSelect: "./src/components/ThemeSelect.astro",
        LanguageSelect: "./src/components/LanguageSelect.astro",
        Header: "./src/components/Header.astro",
        Hero: "./src/components/HomeHero.astro",
        PageTitle: "./src/components/PageTitle.astro",
      },
      description: "Design animated karaoke in Python with WGSL materials, real-time browser previews, and shader exports.",
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/sitiyou/python-kara-templater",
        },
      ],
      customCss: [
        "@fontsource-variable/space-grotesk",
        "@fontsource-variable/plus-jakarta-sans",
        "@fontsource-variable/jetbrains-mono",
        "./src/styles/site.css",
      ],
      sidebar: [
        {
          label: "Start here",
          translations: {"zh-CN": "快速开始"},
          items: [
            {label: "Overview", translations: {"zh-CN": "文档总览"}, slug: "guide"},
            {label: "Quickstart", translations: {"zh-CN": "快速上手"}, slug: "getting-started"},
            {label: "Core concepts", translations: {"zh-CN": "核心概念"}, slug: "concepts"},
            {label: "Effect gallery", translations: {"zh-CN": "特效画廊"}, link: "/gallery/"},
            {label: "Component library", translations: {"zh-CN": "组件库"}, link: "/components/"},
            {label: "Example scripts", translations: {"zh-CN": "示例脚本"}, slug: "examples"},
          ],
        },
        {
          label: "Tutorials",
          translations: {"zh-CN": "实战教程"},
          items: [
            {label: "Tutorials overview", translations: {"zh-CN": "教程导览"}, slug: "tutorials"},
            {
              label: "Design a song layout",
              translations: {"zh-CN": "设计整曲版式"},
              slug: "tutorials/karaoke-design",
            },
            {
              label: "Animate the highlight",
              translations: {"zh-CN": "定制高亮动效"},
              slug: "tutorials/lyric-highlights",
            },
            {
              label: "Write a custom animation",
              translations: {"zh-CN": "编写自定义动画"},
              slug: "tutorials/custom-animation",
            },
            {
              label: "Effect recipes",
              translations: {"zh-CN": "特效配方"},
              slug: "tutorials/effect-recipes",
            },
            {
              label: "Motion studies",
              translations: {"zh-CN": "动效对照研究"},
              slug: "tutorials/lyric-studies",
            },
          ],
        },
        {
          label: "Lyrics & layout",
          translations: {"zh-CN": "歌词与排版"},
          items: [
            {label: "Guides overview", translations: {"zh-CN": "指南总览"}, slug: "guides"},
            {
              label: "Import timed lyrics",
              translations: {"zh-CN": "导入带时间轴的歌词"},
              slug: "guides/documents",
            },
            {
              label: "Lay out vocal tracks",
              translations: {"zh-CN": "布置声部轨道"},
              slug: "guides/tracks",
            },
            {
              label: "Ruby readings and cues",
              translations: {"zh-CN": "注音与倒数提示"},
              slug: "guides/text-and-cues",
            },
            {
              label: "Choose and register fonts",
              translations: {"zh-CN": "选择与注册字体"},
              slug: "guides/fonts",
            },
          ],
        },
        {
          label: "Effects & graphics",
          translations: {"zh-CN": "特效与图形"},
          items: [
            {
              label: "Built-in karaoke effects",
              translations: {"zh-CN": "内置卡拉 OK 特效"},
              slug: "guides/karaoke-effects",
            },
            {
              label: "Colour and materials",
              translations: {"zh-CN": "色彩与材质"},
              slug: "guides/materials",
            },
            {
              label: "Animation and timing",
              translations: {"zh-CN": "动画与时序"},
              slug: "guides/animation",
            },
            {
              label: "Scene objects and groups",
              translations: {"zh-CN": "场景对象与编组"},
              slug: "guides/objects",
            },
            {
              label: "Shapes, clips and masks",
              translations: {"zh-CN": "图形、裁剪与遮罩"},
              slug: "guides/geometry",
            },
            {
              label: "Particles, copies and echoes",
              translations: {"zh-CN": "粒子、副本与回声"},
              slug: "guides/particles",
            },
            {
              label: "Command line",
              translations: {"zh-CN": "命令行工具"},
              slug: "guides/cli",
            },
          ],
        },
        {
          label: "Output & playback",
          translations: {"zh-CN": "输出与播放"},
          items: [
            {label: "Preview and export", translations: {"zh-CN": "预览与导出"}, slug: "output"},
            {
              label: "Play and render a Hook",
              translations: {"zh-CN": "播放与渲染 Hook"},
              slug: "output/hook",
            },
            {
              label: "Export standard ASS",
              translations: {"zh-CN": "导出标准 ASS"},
              slug: "output/ass",
            },
            {
              label: "Troubleshooting",
              translations: {"zh-CN": "故障排查"},
              slug: "output/troubleshooting",
            },
          ],
        },
        {
          label: "Python API",
          translations: {"zh-CN": "Python API"},
          collapsed: true,
          items: [
            {label: "API overview", translations: {"zh-CN": "API 总览"}, slug: "reference"},
            {label: "Documents & lyrics", slug: "reference/documents"},
            {label: "Tracks & effects", slug: "reference/tracks"},
            {label: "Text & layout", slug: "reference/text"},
            {label: "Scenes & compilation", slug: "reference/scenes"},
            {label: "Animation & timing", slug: "reference/animation"},
            {label: "Colors & appearance", slug: "reference/paint"},
            {label: "Geometry & paths", slug: "reference/geometry"},
            {label: "Lyric cues", slug: "reference/cues"},
            {label: "Particles & copies", slug: "reference/particles"},
            {label: "Raster previews", slug: "reference/native"},
          ],
        },
        {
          label: "Contribute",
          translations: {"zh-CN": "参与贡献"},
          collapsed: true,
          items: [
            {label: "Contributor overview", translations: {"zh-CN": "贡献导览"}, slug: "contributing"},
            {label: "Development setup", translations: {"zh-CN": "开发环境搭建"}, slug: "contributing/setup"},
            {label: "Architecture", translations: {"zh-CN": "项目架构"}, slug: "contributing/architecture"},
            {label: "Checks and tests", translations: {"zh-CN": "检查与测试"}, slug: "contributing/checks"},
            {
              label: "Documentation site",
              translations: {"zh-CN": "文档站构建"},
              slug: "contributing/documentation-site",
            },
            {label: "Releases", translations: {"zh-CN": "发布构建"}, slug: "contributing/releasing"},
          ],
        },
      ],
    }),
  ],
});
