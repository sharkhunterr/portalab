import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../../../api/client";
import { FxLayer } from "../../../../design-system/components/Fx";
import { ExternalScript } from "../../../../design-system/visuals/ExternalScript";
import {
  type ExternalElement,
  fxName,
  installElements,
  normaliseElement,
  uninstallScope,
} from "../../../../design-system/visuals/registry";

/**
 * 028 (US5): the booster scene a pack brings — parts drawn *around* what Portalab draws: the sealed
 * booster's look, the stage's animated background, the opening, a reveal effect per rarity, the cards'
 * faces and backs per rarity. The cards drawn, their rarities, names and refunds stay Portalab's own (a scene
 * only ever receives the phase, a rarity and a position). A part the scene does not bring keeps Portalab's.
 */

export type Rarity = "common" | "rare" | "epic" | "legendary";

/** Issue 243: the kind of booster every Mediacards booster is (bought in the shop or given by watching). */
export const CARD_BOOSTER = "card_booster";
type PerRarity = Partial<Record<Rarity, ExternalElement>>;

export interface Scene {
  pack: string;
  look: string;
  parts: {
    booster_look?: ExternalElement;
    backdrop?: ExternalElement;
    opening?: ExternalElement;
    reveal?: PerRarity;
    face?: PerRarity;
    back?: PerRarity;
  };
}

function elementsOf(scene: Scene): ExternalElement[] {
  const { parts } = scene;
  return [
    parts.booster_look,
    parts.backdrop,
    parts.opening,
    ...Object.values(parts.reveal ?? {}),
    ...Object.values(parts.face ?? {}),
    ...Object.values(parts.back ?? {}),
  ].filter((e): e is ExternalElement => Boolean(e));
}

/** The scene this booster opens with — its parts' files loaded while it is open (``null``: Portalab's).
 * ``kind``: the scene of its kind of booster when it has none of its own (``card_booster``, issue 243). */
export function useBoosterScene(boosterKey: string | null | undefined, kind?: string): Scene | null {
  const query = useQuery({
    queryKey: ["visuals", "scene", boosterKey, kind ?? null],
    enabled: Boolean(boosterKey),
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/visuals/scenes/{booster_key}", {
          params: { path: { booster_key: boosterKey as string }, query: kind ? { kind } : {} },
        })
      ).data as unknown as { scene: Scene | null },
  });
  const scene = query.data?.scene ?? null;
  useEffect(() => {
    if (!scene) return;
    void installElements(elementsOf(scene), "scene");
    return () => uninstallScope("scene");
  }, [scene]);
  return scene;
}

/** Issue 153: the scene each booster wears (``*``: every booster without its own) — the look its sealed pack
 * takes in the shop comes from it. */
export interface SceneBinding {
  pack: string;
  look: string;
  names: Record<string, string>;
  /** the look its sealed pack takes (its scene's ``booster_look`` part, when it styles one) */
  booster_look: string | null;
  /** its cards' back — what the shop shows of the booster: a card face down */
  card_back?: string | null;
}

export function useSceneBindings(): Record<string, SceneBinding> {
  const query = useQuery({
    queryKey: ["visuals", "scenes"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/visuals/scenes")).data as unknown as { bindings: Record<string, SceneBinding> },
  });
  return query.data?.bindings ?? {};
}

/** The scene a booster wears: its own, else the one every booster wears — or, for a booster of a ``kind``
 * (``card_booster``: the Mediacards'), the one its kind wears (issue 243). */
export function bindingOf(
  bindings: Record<string, SceneBinding>,
  boosterKey: string,
  kind?: string,
): SceneBinding | undefined {
  return bindings[boosterKey] ?? (kind ? bindings[kind] : bindings["*"]);
}

/**
 * Issue 154: a scene rebuilt from a pack version's own elements (the Test step tries it before it is
 * published) — its parts found by their folder, as the server does for a live one.
 */
export function sceneFrom(elements: ExternalElement[], scene: ExternalElement): Scene {
  const byFolder = new Map(elements.filter((e) => e.folder).map((e) => [String(e.folder), e]));
  const find = (folder: unknown) => byFolder.get(String(folder).replace(/^elements\//, ""));
  const parts: Scene["parts"] = {};
  for (const [slot, value] of Object.entries(scene.parts ?? {})) {
    if (value && typeof value === "object") {
      const perRarity: Partial<Record<Rarity, ExternalElement>> = {};
      for (const [rarity, folder] of Object.entries(value as Record<string, unknown>)) {
        const part = find(folder);
        if (part) perRarity[rarity as Rarity] = part;
      }
      (parts as Record<string, unknown>)[slot] = perRarity;
    } else {
      const part = find(value);
      if (part) (parts as Record<string, unknown>)[slot] = part;
    }
  }
  return { pack: scene.pack, look: scene.look ?? "", parts };
}

/** A part drawn by itself over a place of the scene: a GPU stage, or a script in its sandbox; a CSS part
 * styles its hook (the ``data-*`` attribute the scene sets) and needs nothing here. */
export function ScenePart({
  element,
  context,
  className,
}: {
  element: ExternalElement | undefined;
  context: { reducedMotion: boolean; phase: string; rarity?: string; index?: number; count?: number };
  className: string;
}) {
  if (!element) return null;
  const part = normaliseElement(element);
  if (context.reducedMotion) return null; // reduced motion: the cards show without any of it
  if (part.kind === "glsl") {
    return (
      <span className={className} aria-hidden="true">
        <FxLayer effect={fxName(part)} className="booster-stage__gpu-canvas" />
      </span>
    );
  }
  if (part.kind === "js") {
    return <ExternalScript element={part} context={context} className={className} />;
  }
  return null;
}

/** The look a part sets on its hook, for its stylesheets (a GPU or scripted part may bring some too);
 * ``undefined``: Portalab's own. */
export function hookOf(element: ExternalElement | undefined): string | undefined {
  if (!element) return undefined;
  return element.kind === "css" || (element.css?.length ?? 0) > 0 ? (element.look ?? undefined) : undefined;
}
