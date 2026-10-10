import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** News API hooks (spec 011). */
export type NewsCard = components["schemas"]["NewsCard"];
export type NewsArticle = components["schemas"]["NewsArticleOut"];
export type NewsEditor = components["schemas"]["NewsEditorOut"];
export type NewsArticleIn = components["schemas"]["NewsArticleIn"];

const KEY = ["news"] as const;

export function useNewsList(category?: string) {
  return useQuery({
    queryKey: [...KEY, "list", category],
    queryFn: async () =>
      (await api.GET("/api/v1/news", { params: { query: category ? { category } : {} } })).data ?? {
        items: [],
        next_cursor: null,
      },
  });
}

export function useFeatured() {
  return useQuery({
    queryKey: [...KEY, "featured"],
    queryFn: async () => (await api.GET("/api/v1/news/featured")).data ?? [],
  });
}

export function useCategories() {
  return useQuery({
    queryKey: [...KEY, "categories"],
    queryFn: async () => (await api.GET("/api/v1/news/categories")).data ?? [],
  });
}

export function useArticle(slug: string, lang?: string) {
  return useQuery({
    queryKey: [...KEY, "article", slug, lang],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/news/{slug}", { params: { path: { slug }, query: lang ? { lang } : {} } }))
        .data as NewsArticle,
  });
}

export function useEditorial() {
  return useQuery({
    queryKey: [...KEY, "editorial"],
    queryFn: async () => (await api.GET("/api/v1/admin/news/articles")).data ?? [],
  });
}

export function useNewsActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const save = useMutation({
    mutationFn: async ({ id, body }: { id?: string; body: NewsArticleIn }) =>
      id
        ? (
            await api.PATCH("/api/v1/admin/news/articles/{article_id}", {
              params: { path: { article_id: id } },
              body,
            })
          ).data
        : (await api.POST("/api/v1/admin/news/articles", { body })).data,
    onSettled: settle,
  });
  const publish = useMutation({
    mutationFn: async (id: string) =>
      (
        await api.POST("/api/v1/admin/news/articles/{article_id}/{action}", {
          params: { path: { article_id: id, action: "publish" } },
        })
      ).data,
    onSettled: settle,
  });
  const schedule = useMutation({
    mutationFn: async ({ id, at }: { id: string; at: string }) =>
      (
        await api.POST("/api/v1/admin/news/articles/{article_id}/schedule", {
          params: { path: { article_id: id } },
          body: { publish_at: at },
        })
      ).data,
    onSettled: settle,
  });
  const lifecycle = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "archive" | "restore" }) =>
      (
        await api.POST("/api/v1/admin/news/articles/{article_id}/lifecycle/{action}", {
          params: { path: { article_id: id, action } },
        })
      ).data,
    onSettled: settle,
  });
  const feature = useMutation({
    mutationFn: async ({ id, on }: { id: string; on: boolean }) =>
      on
        ? (
            await api.POST("/api/v1/admin/news/articles/{article_id}/feature", {
              params: { path: { article_id: id } },
              body: { priority: 0 },
            })
          ).data
        : (
            await api.POST("/api/v1/admin/news/articles/{article_id}/unfeature", {
              params: { path: { article_id: id } },
            })
          ).data,
    onSettled: settle,
  });
  return { save, publish, schedule, lifecycle, feature };
}

/** #48: the member opened an article — remembered once; the unread dots go away. */
export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (slug: string) => {
      await api.POST("/api/v1/news/{slug}/read", { params: { path: { slug } } });
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: KEY });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export type NewsReaders = components["schemas"]["NewsReadersOut"];

/** #48: who read an article, and who has not yet (editors). */
export function useReaders(articleId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...KEY, "readers", articleId],
    enabled,
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/news/articles/{article_id}/readers", {
          params: { path: { article_id: articleId } },
        })
      ).data as NewsReaders,
  });
}
