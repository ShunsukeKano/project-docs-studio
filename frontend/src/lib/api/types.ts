// Short names for the generated types. The shapes themselves come from generated/schema.d.ts.
import type { components } from "./generated/schema";

type Schemas = components["schemas"];

export type ArticleDetail = Schemas["ArticleDetail"];
export type ArticleSummary = Schemas["ArticleSummary"];
export type PublishResult = Schemas["PublishResult"];
export type VersionSummary = Schemas["VersionSummary"];
export type VersionDetail = Schemas["VersionDetail"];
export type PublicArticle = Schemas["PublicArticle"];
export type PublicArticleListItem = Schemas["PublicArticleListItem"];
export type ArticleStatus = ArticleDetail["status"];
