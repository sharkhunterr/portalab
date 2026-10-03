import { useEffect, useId, useRef, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { useT } from "../../i18n/hooks/useT";
import { usePreview, useUploadAsset } from "./api";
import { SafeHtml } from "./SafeHtml";

/**
 * Markdown editor (spec 011 T012): a labelled text area with a live preview produced by the **same server
 * pipeline and sanitizer** as saved content (preview parity), and image upload to the owning page/article.
 */
export function MarkdownEditor({
  value,
  onChange,
  ownerRef,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  ownerRef?: string | undefined;
  label: string;
}) {
  const t = useT();
  const id = useId();
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [debounced, setDebounced] = useState(value);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), 400);
    return () => clearTimeout(timer);
  }, [value]);
  const preview = usePreview(tab === "preview" ? debounced : "");
  const upload = useUploadAsset(ownerRef ?? "");
  const onFile = (file: File | undefined) => {
    if (!file || !ownerRef) return;
    upload.mutate(file, {
      onSuccess: (asset) => {
        if (asset) onChange(`${value}\n\n${asset.markdown}\n`);
      },
    });
  };
  return (
    <div className="markdown-editor">
      <div className="ds-stack ds-stack--row" role="toolbar" aria-label={label}>
        <Button
          variant={tab === "write" ? "primary" : "secondary"}
          aria-pressed={tab === "write"}
          onClick={() => setTab("write")}
        >
          {t("content:editor.write")}
        </Button>
        <Button
          variant={tab === "preview" ? "primary" : "secondary"}
          aria-pressed={tab === "preview"}
          onClick={() => setTab("preview")}
        >
          {t("content:editor.preview")}
        </Button>
        {ownerRef ? (
          <>
            <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
              {t("content:editor.image")}
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              hidden
              onChange={(event) => onFile(event.currentTarget.files?.[0])}
            />
          </>
        ) : null}
      </div>
      {tab === "write" ? (
        <>
          <label htmlFor={id}>{label}</label>
          <textarea
            id={id}
            className="markdown-editor__input"
            value={value}
            rows={18}
            onChange={(e) => onChange(e.target.value)}
          />
        </>
      ) : (
        <section aria-label={t("content:editor.preview")} className="markdown-editor__preview">
          {preview.data ? <SafeHtml html={preview.data.html} diagrams /> : null}
          {preview.data?.warnings.includes("possible_secret") ? (
            <p role="status">{t("content:editor.sensitiveWarning")}</p>
          ) : null}
        </section>
      )}
      {upload.isError ? <p role="alert">{t("content:editor.uploadFailed")}</p> : null}
    </div>
  );
}
