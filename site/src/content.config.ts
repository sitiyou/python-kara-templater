import {defineCollection} from "astro:content";
import {glob} from "astro/loaders";
import {i18nLoader} from "@astrojs/starlight/loaders";
import {docsSchema, i18nSchema} from "@astrojs/starlight/schema";

export const collections = {
  docs: defineCollection({
    loader: glob({base: "../build/docs-site/content", pattern: "**/*.md"}),
    schema: docsSchema(),
  }),
  i18n: defineCollection({loader: i18nLoader(), schema: i18nSchema()}),
};
