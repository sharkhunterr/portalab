import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** issue 316: self-writing newsletter editions — their templates, previews, drafts and the published ones. */
export type Template = components["schemas"]["TemplateOut"];
export type Definition = components["schemas"]["TemplateDefinition"];
export type Section = components["schemas"]["Section"];
export type Edition = components["schemas"]["EditionOut"];

const TEMPLATES = ["admin", "news", "edition-templates"] as const;
const EDITIONS = ["news", "editions"] as const;

/** A template's name: the built-in ones in the interface's language. */
export function templateName(t: (key: string) => string, template: Template): string {
  if (!template.builtin) return template.definition.name;
  const name = t(`news:edition.template.${template.key}.name`);
  return name.startsWith("news:") || name.startsWith("edition.") ? template.definition.name : name;
}

export function templateAbout(t: (key: string) => string, template: Template): string {
  if (!template.builtin) return template.definition.description ?? "";
  const about = t(`news:edition.template.${template.key}.description`);
  return about.startsWith("news:") || about.startsWith("edition.")
    ? (template.definition.description ?? "")
    : about;
}

export function useTemplates() {
  return useQuery({
    queryKey: TEMPLATES,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/news/newsletter-templates")).data ?? []) as Template[],
  });
}

export function useSaveTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, definition }: { key: string; definition: Definition }) => {
      const { error } = await api.PUT("/api/v1/admin/news/newsletter-templates/{key}", {
        params: { path: { key } },
        body: definition,
      });
      if (error) throw error;
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: TEMPLATES }),
  });
}

export function useDeleteTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) => {
      await api.DELETE("/api/v1/admin/news/newsletter-templates/{key}", { params: { path: { key } } });
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: TEMPLATES }),
  });
}

export interface EditionAsk {
  template_key: string;
  days: number;
  language: string;
  notice?: string | null;
  category_id?: string | null;
  definition?: Definition | null;
  /** issue 323: what it tells (none: the template's own sections). */
  contents?: Content[] | null;
  /** issue 324: its statistics' charts (none: the usual ones). */
  charts?: Chart[] | null;
}

export type Chart = NonNullable<components["schemas"]["EditionIn"]["charts"]>[number];

export type Content = NonNullable<components["schemas"]["EditionIn"]["contents"]>[number];

/** issue 323: what an edition may tell, in its order, and what is on by default. */
export function useContents() {
  return useQuery({
    queryKey: ["admin", "news", "edition-contents"],
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/news/newsletter-contents")).data as {
        contents: Content[];
        defaults: Content[];
        charts: Chart[];
        chart_defaults: Chart[];
      },
  });
}

/** A preview — of a saved template, or of one being written — whose page the news desk frames. */
export function usePreview() {
  return useMutation({
    mutationFn: async (ask: EditionAsk) => {
      const { data, error } = await api.POST("/api/v1/admin/news/newsletter-editions/preview", { body: ask });
      if (error) throw error;
      return data as Edition;
    },
  });
}

export function useAdminEditions() {
  return useQuery({
    queryKey: [...EDITIONS, "admin"],
    queryFn: async () => ((await api.GET("/api/v1/admin/news/newsletter-editions")).data ?? []) as Edition[],
  });
}

export function useEditionActions() {
  const client = useQueryClient();
  const done = () => void client.invalidateQueries({ queryKey: EDITIONS });
  return {
    create: useMutation({
      mutationFn: async (ask: EditionAsk) => {
        const { data, error } = await api.POST("/api/v1/admin/news/newsletter-editions", {
          body: { ...ask, definition: undefined },
        });
        if (error) throw error;
        return data as Edition;
      },
      onSuccess: done,
    }),
    publish: useMutation({
      mutationFn: async ({ id, email }: { id: string; email: boolean }) => {
        const { error } = await api.POST("/api/v1/admin/news/newsletter-editions/{edition_id}/publish", {
          params: { path: { edition_id: id } },
          body: { email },
        });
        if (error) throw error;
      },
      onSuccess: done,
    }),
    // issue 317: the edition e-mailed to me alone
    test: useMutation({
      mutationFn: async (id: string) => {
        const { data, error } = await api.POST("/api/v1/admin/news/newsletter-editions/{edition_id}/test", {
          params: { path: { edition_id: id } },
        });
        if (error) throw error;
        return Boolean((data as { sent?: boolean } | undefined)?.sent);
      },
    }),
    remove: useMutation({
      mutationFn: async (id: string) => {
        await api.DELETE("/api/v1/admin/news/newsletter-editions/{edition_id}", {
          params: { path: { edition_id: id } },
        });
      },
      onSuccess: done,
    }),
  };
}

export function useEditions() {
  return useQuery({
    queryKey: [...EDITIONS, "published"],
    queryFn: async () => ((await api.GET("/api/v1/news/editions")).data ?? []) as Edition[],
  });
}

export function useEdition(id: string) {
  return useQuery({
    queryKey: [...EDITIONS, id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/news/editions/{edition_id}", {
        params: { path: { edition_id: id } },
      });
      if (error) throw error;
      return data as Edition;
    },
  });
}
