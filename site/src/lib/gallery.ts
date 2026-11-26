import entries from "../../../build/docs-site/gallery.json";
import {assetUrl, type Locale, url} from "./i18n";

export interface DemoTranslation {
  title?: string;
  short?: string;
  category?: string;
  summary?: string;
  details?: string;
  labels?: Record<string, string>;
}

export interface Demo {
  id: string;
  title: string;
  short?: string;
  category: string;
  summary: string;
  details: string;
  source: string;
  guide: string;
  accent: string;
  still: number;
  width: number;
  height: number;
  code: string;
  command: string;
  labels?: Record<string, string>;
  "zh-cn"?: DemoTranslation;
}

export interface LocalizedDemo extends Demo {
  shortTitle: string;
  rawCategory: string;
}

export const demos: Demo[] = entries;

export function localizeDemo(demo: Demo, locale: Locale): LocalizedDemo {
  const tr = locale === "zh-cn" ? demo["zh-cn"] : undefined;
  const labels = tr?.labels ?? demo.labels;
  const title = tr?.title ?? demo.title;
  return {
    ...demo,
    rawCategory: demo.category,
    title,
    shortTitle: tr?.short ?? demo.short ?? title,
    category: tr?.category ?? demo.category,
    summary: tr?.summary ?? demo.summary,
    details: tr?.details ?? demo.details,
    labels,
  };
}

export function previewUrl(demo: Pick<Demo, "id">): string {
  return assetUrl(`previews/${demo.id}/`);
}

export {url};
