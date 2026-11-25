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
    interactiveBadge: string;
    moreLink: string;
    errorStatus: string;
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
        {label: "教程", href: url("tutorials/", locale), match: "/zh-cn/tutorials"},
        {label: "指南", href: url("guides/", locale), match: "/zh-cn/guides"},
        {label: "API", href: url("reference/", locale), match: "/zh-cn/reference"},
      ],
      hero: {
        eyebrow: "libplacebo Hook · Python 3.12+ · ASS",
        titlePrefix: "用 Python 编排",
        titleSweep: "舞台级卡拉 OK",
        titleSuffix: "字幕特效",
        tagline: "从带时间轴的 ASS 歌词出发，套用内置预设，或自由组合声部排版、振假名、粒子与 WGSL 材质。导出独立 libplacebo Hook，直接在 mpv 播放或交由 FFmpeg 渲染。",
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
            symbol: "Hook / ASS",
            title: "实时播放或渲染成片",
            body: "默认导出独立 libplacebo Hook 供 mpv 与 FFmpeg 使用，也支持导出标准 ASS。",
            href: url("output/", locale),
          },
        ],
        codeEyebrow: "极简模板",
        codeTitle: "十几行 Python，写出带注音的双色走字",
        codeBody: "常用卡拉 OK 行为均内置合理默认值：字体度量、振假名对齐与音节边界自动计算，只需专注于色彩、节奏与版式。",
        codeAction: "查看完整快速上手",
        codeFeatures: [
          {label: "自动度量", detail: "原生文本整形计算每个音节与振假名的准确像素范围。"},
          {label: "独立着色器 Hook", detail: "无需额外插件，mpv 与 FFmpeg 直接加载渲染。"},
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
            body: "了解 Hook 与标准 ASS 的边界，查阅 mpv 播放与 FFmpeg 压制命令。",
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
        lede: "由真实 Python 示例构建的实时预览，与导出后的 libplacebo Hook 共用同一套着色与计时逻辑。",
        allFilter: "全部",
        filterAria: "按特效分类筛选",
        interactiveBadge: "支持实时调参",
        moreLink: "更多示例与长篇动效研究",
        errorStatus: "部分缩略图暂时不可用，仍可点开查看源码。",
        breadcrumbHome: "特效画廊",
        howItWorks: "原理",
        readGuide: "指南",
        viewSource: "源码",
        runTitle: "本地导出",
        runIntro: "下载脚本并运行，即可导出独立 libplacebo Hook。",
        rubyFontNote: "建议安装 Noto Sans CJK JP 以完整匹配日文字形。",
        downloadLabel: "下载",
        sourceTitle: "源码",
        relatedTitle: "更多特效",
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
      {label: "Tutorials", href: url("tutorials/", locale), match: "/tutorials"},
      {label: "Guides", href: url("guides/", locale), match: "/guides"},
      {label: "API", href: url("reference/", locale), match: "/reference"},
    ],
    hero: {
      eyebrow: "libplacebo Hook · Python 3.12+ · Timed ASS",
      titlePrefix: "Stage-grade",
      titleSweep: "karaoke effects",
      titleSuffix: "in Python",
      tagline: "Turn timed ASS lyrics into animated karaoke overlays. Apply a preset or compose vocal tracks, ruby readings, particles, and WGSL shaders — then export a standalone libplacebo Hook for mpv and FFmpeg.",
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
          symbol: "Hook / ASS",
          title: "Play or render anywhere",
          body: "Export a standalone libplacebo Hook for mpv and FFmpeg, or compile standard ASS.",
          href: url("output/", locale),
        },
      ],
      codeEyebrow: "Minimal template",
      codeTitle: "Twelve lines for ruby-synced duotone sweep",
      codeBody: "Common karaoke behaviour lives in library defaults. Native text shaping measures every syllable and ruby reading automatically, so your script stays focused on colour, rhythm, and layout.",
      codeAction: "Follow the quickstart",
      codeFeatures: [
        {label: "Native glyph metrics", detail: "Measures real shaped advances for CJK, Latin, and ruby readings."},
        {label: "Standalone GPU Hook", detail: "No player plugins required — load directly in mpv or FFmpeg."},
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
          body: "Compare Hook vs standard ASS, run mpv and FFmpeg commands, and fix common issues.",
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
      lede: "Built straight from runnable Python scripts with the same shader and timing contract as exported Hooks.",
      allFilter: "All",
      filterAria: "Filter by effect category",
      interactiveBadge: "Live controls",
      moreLink: "More examples & motion studies",
      errorStatus: "Some thumbnails are unavailable. Every example page and script is still accessible.",
      breadcrumbHome: "Gallery",
      howItWorks: "How it works",
      readGuide: "Guide",
      viewSource: "Source",
      runTitle: "Export locally",
      runIntro: "Download the script and run this command to export a standalone Hook.",
      rubyFontNote: "Install Noto Sans CJK JP to match the Japanese preview glyphs.",
      downloadLabel: "Download",
      sourceTitle: "Source",
      relatedTitle: "More effects",
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
