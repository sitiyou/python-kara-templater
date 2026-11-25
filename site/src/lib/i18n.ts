export type Locale = "en" | "zh-cn";

export function detectLocale(routeLocale?: string): Locale {
  return routeLocale === "zh-cn" ? "zh-cn" : "en";
}

export function baseUrl(): string {
  return import.meta.env.BASE_URL.replace(/\/$/, "");
}

export function url(path: string, locale: Locale = "en"): string {
  const clean = path.replace(/^\/+/, "");
  const prefix = locale === "zh-cn" ? "/zh-cn" : "";
  if (!clean) return `${baseUrl()}${prefix}/`;
  return `${baseUrl()}${prefix}/${clean}`;
}

export function assetUrl(path: string): string {
  return `${baseUrl()}/${path.replace(/^\/+/, "")}`;
}

export interface UiStrings {
  nav: Array<{label: string; href: string; match: string}>;
  hero: {
    eyebrow: string;
    titlePrefix: string;
    titleSweep: string;
    titleSuffix: string;
    tagline: string;
    primaryCta: string;
    secondaryCta: string;
    cliLabel: string;
    stageOpen: string;
    stageSwitchLabel: string;
    liveTag: string;
  };
  home: {
    pipelineEyebrow: string;
    pipelineTitle: string;
    pipelineSteps: Array<{step: string; symbol: string; title: string; body: string; href: string}>;
    codeEyebrow: string;
    codeTitle: string;
    codeBody: string;
    codeAction: string;
    codeFeatures: Array<{label: string; detail: string}>;
    pathsEyebrow: string;
    pathsTitle: string;
    paths: Array<{title: string; body: string; href: string; badge: string}>;
  };
  gallery: {
    title: string;
    description: string;
    eyebrow: string;
    lede: string;
    allFilter: string;
    filterAria: string;
    moreLink: string;
    breadcrumbHome: string;
    howItWorks: string;
    readGuide: string;
    viewSource: string;
    runTitle: string;
    runIntro: string;
    rubyFontNote: string;
    downloadLabel: string;
    sourceTitle: string;
    relatedTitle: string;
  };
  components: {
    title: string;
    description: string;
    navigation: string;
    groups: Record<string, string>;
    groupHints: Record<string, string>;
    groupDetails: Record<string, string>;
    search: string;
    matches: string;
    noMatches: string;
    sampled: string;
    assPreview: string;
    reference: string;
    componentSource: string;
    galleryExample: string;
  };
  preview: {
    play: string;
    pause: string;
    loading: string;
    noscript: string;
    unavailable: string;
    seekLabel: string;
    secondsUnit: string;
    adjustTitle: string;
    reset: string;
    playCard: string;
    pauseCard: string;
    autoPlay: string;
    autoPause: string;
  };
  notFound: {
    title: string;
    lede: string;
    start: string;
    gallery: string;
    api: string;
  };
}

export function getUi(locale: Locale): UiStrings {
  if (locale === "zh-cn") {
    return {
      nav: [
        {label: "快速上手", href: url("getting-started/", locale), match: "/zh-cn/getting-started"},
        {label: "特效画廊", href: url("gallery/", locale), match: "/zh-cn/gallery"},
        {label: "组件库", href: url("components/", locale), match: "/zh-cn/components"},
        {label: "教程", href: url("tutorials/", locale), match: "/zh-cn/tutorials"},
        {label: "指南", href: url("guides/", locale), match: "/zh-cn/guides"},
        {label: "API", href: url("reference/", locale), match: "/zh-cn/reference"},
      ],
      hero: {
        eyebrow: "WGSL · Python 3.12+",
        titlePrefix: "用 Python 编排",
        titleSweep: "舞台级卡拉 OK",
        titleSuffix: "字幕特效",
        tagline: "用 Python 编排带时间轴的歌词，组合走字、注音和粒子，用 WGSL 编写自定义材质。在浏览器里实时预览，也可导出着色器用于视频播放和压制。",
        primaryCta: "快速上手",
        secondaryCta: "特效画廊",
        cliLabel: "一行命令试跑预设",
        stageOpen: "查看参数与源码",
        stageSwitchLabel: "切换预览特效",
        liveTag: "WebGL 2",
      },
      home: {
        pipelineEyebrow: "核心工作流",
        pipelineTitle: "四个清晰步骤，从时间轴直达画面",
        pipelineSteps: [
          {
            step: "01",
            symbol: "Document",
            title: "导入带时间轴的歌词",
            body: "读取含 \\k 计时与注音标记的 ASS 文件，保留精确音节边界与来源位置。",
            href: url("guides/documents/", locale),
          },
          {
            step: "02",
            symbol: "Track",
            title: "编排声部与排版",
            body: "为主唱、和声与倒数提示分配独立轨道、字体度量与振假名间距。",
            href: url("guides/tracks/", locale),
          },
          {
            step: "03",
            symbol: "Scene",
            title: "组合走字、动效与材质",
            body: "叠加柔边扫色、双色辉光、粒子发射、曲线动画与自定义 WGSL 着色器。",
            href: url("guides/karaoke-effects/", locale),
          },
          {
            step: "04",
            symbol: "Naga",
            title: "实时预览与导出",
            body: "Naga 将 WGSL 材质转译为 GLSL，供浏览器实时预览或打包到播放文件。需要普通字幕时，可导出标准 ASS。",
            href: url("output/", locale),
          },
        ],
        codeEyebrow: "极简模板",
        codeTitle: "十几行 Python，写出带注音的双色走字",
        codeBody: "常用卡拉 OK 行为均内置合理默认值：字体度量、振假名对齐与音节边界自动计算，只需专注于色彩、节奏与版式。",
        codeAction: "查看完整快速上手",
        codeFeatures: [
          {label: "自动度量", detail: "原生文本整形计算每个音节与振假名的准确像素范围。"},
          {label: "浏览器实时预览", detail: "调用 scene.preview()，即可在浏览器中播放场景并拖动时间轴。"},
          {label: "无损复现", detail: "按时间戳纯函数求值，拖拽进度条与连续播放完全一致。"},
        ],
        pathsEyebrow: "按目标阅读",
        pathsTitle: "接下来你想做什么？",
        paths: [
          {
            badge: "教程",
            title: "从零设计整曲模板",
            body: "一步步搭建主唱、和声、振假名与倒数提示，并对照八种动效配方。",
            href: url("tutorials/", locale),
          },
          {
            badge: "指南",
            title: "深入歌词、动效与材质",
            body: "按主题查阅轨道布局、字体选择、动画时钟、遮罩、粒子与 WGSL 材质。",
            href: url("guides/", locale),
          },
          {
            badge: "输出",
            title: "播放、渲染与故障排查",
            body: "打开本地预览，查阅 mpv 播放、FFmpeg 压制和标准 ASS 导出的用法。",
            href: url("output/", locale),
          },
          {
            badge: "参考",
            title: "查阅 Python API 签名",
            body: "按模块与字母检索所有公开类、函数、字段类型与默认值（英文参考）。",
            href: url("reference/", locale),
          },
        ],
      },
      gallery: {
        title: "特效画廊",
        description: "在浏览器中直接播放卡拉 OK 特效、实时调节着色器参数并下载对应的 Python 脚本。",
        eyebrow: "WebGL 2",
        lede: "卡片会循环播放效果片段。点开示例可实时渲染、拖动时间轴、调节可用参数并下载源码。",
        allFilter: "全部",
        filterAria: "按特效分类筛选",
        moreLink: "更多示例与长篇动效研究",
        breadcrumbHome: "特效画廊",
        howItWorks: "原理",
        readGuide: "指南",
        viewSource: "源码",
        runTitle: "本地导出",
        runIntro: "下载并运行脚本，即可导出供 mpv 和 FFmpeg 使用的 .hook 文件。",
        rubyFontNote: "建议安装 Noto Sans CJK JP 以完整匹配日文字形。",
        downloadLabel: "下载",
        sourceTitle: "源码",
        relatedTitle: "更多特效",
      },
      components: {
        title: "组件库",
        description: "按类别预览内置预设和可组合的 Python 组件。入场、退场、走字和装饰使用同一句带时间轴的歌词，方便对比。",
        navigation: "选择组件类别",
        groups: {
          entry: "入场",
          exit: "退场",
          highlight: "走字与高亮",
          sweep: "走字前沿与扫描线",
          motion: "动画",
          decoration: "节拍装饰",
          cues: "倒数提示",
          particles: "粒子与回声",
          typography: "字体与字形样式",
          paint: "色彩与材质",
          layout: "歌词排版",
          geometry: "路径与遮罩",
        },
        groupHints: {
          entry: "滑入 · 淡入",
          exit: "漂移 · 消散",
          highlight: "扫色 · 音节弹动",
          sweep: "色带 · 羽化",
          motion: "补间 · 路径运动",
          decoration: "起音星光 · 涟漪",
          cues: "数字 · 指示灯",
          particles: "发射 · 延时副本",
          typography: "斜体 · 描边 · 模糊",
          paint: "渐变 · 辉光 · 着色器",
          layout: "双行 · 注音",
          geometry: "裁剪 · 路径变形",
        },
        groupDetails: {
          typography: "每张卡片左侧为基准，右侧展示样式变化。",
          sweep: "左侧为对照，右侧展示当前设置。扫描线是在扫色前沿移动的一条色带。羽化则让唱前色与唱后色在前沿逐渐过渡。",
        },
        search: "搜名称或参数，例如 blur",
        matches: "找到 {count} 个组件",
        noMatches: "没有找到匹配的组件。",
        sampled: "逐帧求值预览",
        assPreview: "标准 ASS 预览",
        reference: "API 参考",
        componentSource: "下载预设与组件示例",
        galleryExample: "画廊示例",
      },
      preview: {
        play: "播放",
        pause: "暂停",
        loading: "加载中…",
        noscript: "启用 JavaScript 即可播放实时预览。",
        unavailable: "当前环境不支持 WebGL 2 预览，仍可查看或下载源码。",
        seekLabel: "播放时间",
        secondsUnit: "s",
        adjustTitle: "参数",
        reset: "重置参数",
        playCard: "播放「{title}」",
        pauseCard: "暂停「{title}」",
        autoPlay: "开启自动播放",
        autoPause: "暂停全部预览",
      },
      notFound: {
        title: "页面未找到",
        lede: "你访问的文档页面可能已经移动或更名，可以从下方入口重新开始。",
        start: "快速上手",
        gallery: "特效画廊",
        api: "Python API",
      },
    };
  }

  return {
    nav: [
      {label: "Quickstart", href: url("getting-started/", locale), match: "/getting-started"},
      {label: "Gallery", href: url("gallery/", locale), match: "/gallery"},
      {label: "Components", href: url("components/", locale), match: "/components"},
      {label: "Tutorials", href: url("tutorials/", locale), match: "/tutorials"},
      {label: "Guides", href: url("guides/", locale), match: "/guides"},
      {label: "API", href: url("reference/", locale), match: "/reference"},
    ],
    hero: {
      eyebrow: "WGSL · Python 3.12+",
      titlePrefix: "Stage-grade",
      titleSweep: "karaoke effects",
      titleSuffix: "in Python",
      tagline: "Turn timed lyrics into karaoke effects in Python. Compose wipes, ruby readings, and particles, or write custom materials in WGSL. Preview live in your browser and export a shader for video playback or rendering.",
      primaryCta: "Get started",
      secondaryCta: "Explore gallery",
      cliLabel: "Try a preset in one command",
      stageOpen: "Inspect parameters & source",
      stageSwitchLabel: "Switch featured preview",
      liveTag: "Live WebGL 2 preview",
    },
    home: {
      pipelineEyebrow: "How it works",
      pipelineTitle: "Four stages from timed lyrics to screen",
      pipelineSteps: [
        {
          step: "01",
          symbol: "Document",
          title: "Import timed lyrics",
          body: "Load ASS files with \\k timing and ruby markers while preserving exact syllable ranges.",
          href: url("guides/documents/", locale),
        },
        {
          step: "02",
          symbol: "Track",
          title: "Lay out vocal streams",
          body: "Place lead, harmony, ruby readings, and count-ins with native font metrics.",
          href: url("guides/tracks/", locale),
        },
        {
          step: "03",
          symbol: "Scene",
          title: "Compose motion & paint",
          body: "Layer soft wipes, blended halos, particles, custom curves, and WGSL shaders.",
          href: url("guides/karaoke-effects/", locale),
        },
        {
          step: "04",
          symbol: "Naga",
          title: "Preview live and export",
          body: "Naga translates WGSL materials to GLSL for browser preview and playback exports. Standard ASS is available for subtitle delivery.",
          href: url("output/", locale),
        },
      ],
      codeEyebrow: "Minimal template",
      codeTitle: "Twelve lines for ruby-synced duotone sweep",
      codeBody: "Common karaoke behaviour lives in library defaults. Native text shaping measures every syllable and ruby reading automatically, so your script stays focused on colour, rhythm, and layout.",
      codeAction: "Follow the quickstart",
      codeFeatures: [
        {label: "Native glyph metrics", detail: "Measures real shaped advances for CJK, Latin, and ruby readings."},
        {label: "Live browser preview", detail: "Call scene.preview() to play and scrub the scene in your browser."},
        {label: "Seek-safe evaluation", detail: "Pure timestamp evaluation keeps scrubbing identical to continuous playback."},
      ],
      pathsEyebrow: "Explore the docs",
      pathsTitle: "Pick where to start",
      paths: [
        {
          badge: "Tutorials",
          title: "Design a song template",
          body: "Build lead, harmony, ruby, and count-ins step by step, then browse reusable effect recipes.",
          href: url("tutorials/", locale),
        },
        {
          badge: "Guides",
          title: "Master layout, motion & shaders",
          body: "Deep dives on Tracks, fonts, built-in effects, materials, clips, particles, and the CLI.",
          href: url("guides/", locale),
        },
        {
          badge: "Output",
          title: "Play, render & troubleshoot",
          body: "Open a local preview, play over video with mpv, render with FFmpeg, or export standard ASS.",
          href: url("output/", locale),
        },
        {
          badge: "Reference",
          title: "Look up the Python API",
          body: "Browse every public class, function, field type, and default grouped by topic.",
          href: url("reference/", locale),
        },
      ],
    },
    gallery: {
      title: "Effect gallery",
      description: "Play live karaoke effects in your browser, tune shader controls, and download the runnable Python behind them.",
      eyebrow: "WebGL 2",
      lede: "Each card loops a clip of the effect. Open an example to render it live, scrub the timeline, tune available controls, and download the Python source.",
      allFilter: "All",
      filterAria: "Filter by effect category",
      moreLink: "More examples & motion studies",
      breadcrumbHome: "Gallery",
      howItWorks: "How it works",
      readGuide: "Guide",
      viewSource: "Source",
      runTitle: "Export locally",
      runIntro: "Download the script and run this command to export a .hook file for mpv or FFmpeg.",
      rubyFontNote: "Install Noto Sans CJK JP to match the Japanese preview glyphs.",
      downloadLabel: "Download",
      sourceTitle: "Source",
      relatedTitle: "More effects",
    },
    components: {
      title: "Component library",
      description: "Browse built-in presets and reusable Python components. Entrances, exits, highlights, and timing ornaments use the same timed lyric for comparison.",
      navigation: "Choose a component category",
      groups: {
        entry: "Entrances",
        exit: "Exits",
        highlight: "Wipes and highlights",
        sweep: "Sweep fronts and scanlines",
        motion: "Animation",
        decoration: "Timing ornaments",
        cues: "Countdown cues",
        particles: "Particles and echoes",
        typography: "Typography",
        paint: "Colour and materials",
        layout: "Lyric layout",
        geometry: "Paths and masks",
      },
      groupHints: {
        entry: "Slide in · Fade in",
        exit: "Drift away · Dissolve",
        highlight: "Colour wipes · Note pulses",
        sweep: "Moving bands · Feathering",
        motion: "Tweens · Motion paths",
        decoration: "Onset stars · Ripples",
        cues: "Numbers · Lamps",
        particles: "Emitters · Delayed copies",
        typography: "Italic · Outline · Blur",
        paint: "Gradients · Glow · Shaders",
        layout: "Alternating rows · Ruby",
        geometry: "Clips · Path deformation",
      },
      groupDetails: {
        typography: "Compare the baseline on the left with the styled text on the right.",
        sweep: "Compare the reference on the left with the variant on the right. A scanline adds a moving band at the wipe front. Feathering blends the waiting and sung colours across the front.",
      },
      search: "Search names or parameters, e.g. blur",
      matches: "{count} matching components",
      noMatches: "No matching components.",
      sampled: "Frame-sampled preview",
      assPreview: "Standard ASS preview",
      reference: "API reference",
      componentSource: "Download presets and component examples",
      galleryExample: "Gallery example",
    },
    preview: {
      play: "Play",
      pause: "Pause",
      loading: "Loading…",
      noscript: "Enable JavaScript to play the live preview.",
      unavailable: "WebGL 2 preview is unavailable. You can still read or download the example.",
      seekLabel: "Playback time",
      secondsUnit: "s",
      adjustTitle: "Controls",
      reset: "Reset parameters",
      playCard: "Play {title}",
      pauseCard: "Pause {title}",
      autoPlay: "Enable autoplay",
      autoPause: "Pause all previews",
    },
    notFound: {
      title: "Page not found",
      lede: "The page you looked for may have moved during the documentation reorganization.",
      start: "Quickstart",
      gallery: "Effect gallery",
      api: "Python API",
    },
  };
}

export function sectionEyebrow(id: string, locale: Locale): string {
  const clean = id.replace(/^zh-cn\//, "");
  const zh = locale === "zh-cn";
  if (clean.startsWith("tutorials")) return zh ? "实战教程" : "Tutorial";
  if (clean.startsWith("guides/documents") || clean.startsWith("guides/tracks") || clean.startsWith("guides/text-and-cues") || clean.startsWith("guides/fonts")) {
    return zh ? "指南 · 歌词与排版" : "Guide · Lyrics & Layout";
  }
  if (clean.startsWith("guides/cli")) return zh ? "指南 · 工具" : "Guide · Tools";
  if (clean.startsWith("guides")) return zh ? "指南 · 特效与图形" : "Guide · Effects";
  if (clean.startsWith("output")) return zh ? "输出与播放" : "Output & Playback";
  if (clean.startsWith("reference")) return zh ? "Python API 参考" : "Python API Reference";
  if (clean.startsWith("contributing")) return zh ? "参与贡献" : "Contributing";
  if (clean.startsWith("examples")) return zh ? "示例脚本" : "Examples";
  return zh ? "快速开始" : "Start Here";
}
