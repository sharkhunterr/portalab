import { useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { externalFx, fxName, normaliseElement } from "../../../design-system/visuals/registry";
import { runSandbox } from "../../../design-system/visuals/sandbox";
import { useT } from "../../../i18n/hooks/useT";
import { ProductArt } from "../../marketplace/catalog/ProductArt";
import { TryOn } from "../../marketplace/product/ProductSheet";
import { type Measure, packPath, useVisualAction, type VersionDetail } from "../api";
import { asProduct, nameOf, OutcomeBadge } from "../parts";

const READY_MS = 4000;
const FPS_MS = 3000;

/** A script's readiness in its sandbox: how long it takes to say it is ready (4 s at most). */
function scriptReady(element: ReturnType<typeof normaliseElement>): Promise<Measure> {
  return new Promise((resolve) => {
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.style.cssText = "position:fixed;width:320px;height:240px;left:-9999px;top:0;border:0";
    document.body.append(frame);
    const started = performance.now();
    let done = false;
    const finish = (measure: Measure) => {
      if (done) return;
      done = true;
      sandbox.stop();
      frame.remove();
      resolve(measure);
    };
    const sandbox = runSandbox(
      frame,
      element,
      { type: element.type, look: element.look, reducedMotion: false, level: 12, text: "+40 XP" },
      {
        onReady: () =>
          finish({ element: element.product, kind: "js", ready_ms: Math.round(performance.now() - started) }),
        onError: (message) => finish({ element: element.product, kind: "js", errors: [message] }),
      },
    );
    window.setTimeout(() => finish({ element: element.product, kind: "js", errors: ["timeout"] }), READY_MS);
  });
}

/** Test: every element drawn as members see it (tried on oneself, never saved), then measured in this
 * browser — each GPU look compiled, each script's readiness, the frames per second while all are shown. */
export function TestStep({ detail }: { detail: VersionDetail }) {
  const t = useT();
  const action = useVisualAction();
  const [running, setRunning] = useState(false);
  const measures = detail.measures?.results ?? [];
  const byElement = new Map(measures.map((m) => [m.element, m]));

  const measure = async () => {
    setRunning(true);
    try {
      const out: Measure[] = [];
      const [{ fxFragment }, { COMMON }] = await Promise.all([
        import("../../../design-system/themes/premium/badgeFx"),
        import("../../../design-system/themes/premium/shaders"),
      ]);
      const gl = document.createElement("canvas").getContext("webgl");
      for (const raw of detail.elements) {
        const element = normaliseElement(raw);
        if (element.kind === "js") {
          out.push(await scriptReady(element));
          continue;
        }
        if (element.kind !== "glsl") {
          out.push({ element: element.product, kind: element.kind });
          continue;
        }
        const name = fxName(element);
        const fx = externalFx(name);
        if (!gl || !fx) {
          out.push({
            element: element.product,
            kind: "glsl",
            compiled: false,
            errors: [gl ? "not loaded" : "no WebGL"],
          });
          continue;
        }
        const shader = gl.createShader(gl.FRAGMENT_SHADER);
        if (!shader) continue;
        gl.shaderSource(shader, fx.ambient ? `${COMMON}${fx.body}` : fxFragment(name));
        gl.compileShader(shader);
        const compiled = Boolean(gl.getShaderParameter(shader, gl.COMPILE_STATUS));
        out.push({
          element: element.product,
          kind: "glsl",
          compiled,
          ...(compiled ? {} : { errors: [(gl.getShaderInfoLog(shader) ?? "").slice(0, 300)] }),
        });
        gl.deleteShader(shader);
      }
      // the frames per second of this page while every element is drawn
      const fps = await new Promise<number>((resolve) => {
        let frames = 0;
        const start = performance.now();
        const tick = (now: number) => {
          frames += 1;
          if (now - start < FPS_MS) requestAnimationFrame(tick);
          else resolve(Math.round((frames * 1000) / (now - start)));
        };
        requestAnimationFrame(tick);
      });
      await action.mutateAsync({
        path: `${packPath(detail.pack, detail.version)}/measures`,
        body: { results: out.map((m) => ({ ...m, fps })) },
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <AdminSection
      title={t("admin:visuals.step.test")}
      icon="eye"
      actions={
        <>
          <OutcomeBadge outcome={detail.outcomes.test ?? "todo"} />
          <Button variant="secondary" disabled={running} onClick={() => void measure()}>
            <Icon name="gauge" size={16} />{" "}
            {running ? t("admin:visuals.test.running") : t("admin:visuals.test.run")}
          </Button>
        </>
      }
      description={t("admin:visuals.test.help")}
    >
      <ul className="visuals-elements">
        {detail.report.elements.map((element) => {
          const result = byElement.get(element.product);
          return (
            <li className="visuals-element" key={element.product}>
              <div className="visuals-element__art">
                <ProductArt product={asProduct(element, element.economy)} size="card" />
              </div>
              <div className="visuals-element__body">
                <p className="visuals-element__name">
                  {nameOf(element.names, element.product)}
                  <span className="visuals-element__type">{t(`admin:visuals.kind.${element.kind}`)}</span>
                </p>
                {result ? (
                  <p
                    className="visuals-element__meta"
                    data-failed={Boolean(result.errors?.length) || undefined}
                  >
                    {result.errors?.length
                      ? t("admin:visuals.test.failed", { detail: result.errors.join(" ") })
                      : result.kind === "glsl"
                        ? t("admin:visuals.test.compiled", { fps: result.fps ?? "?" })
                        : result.kind === "js"
                          ? t("admin:visuals.test.ready", { ms: result.ready_ms ?? "?" })
                          : t("admin:visuals.test.shown")}
                  </p>
                ) : null}
                <div className="ds-stack--row">
                  <TryOn product={asProduct(element, element.economy)} />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </AdminSection>
  );
}
