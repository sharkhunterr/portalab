import { type FormEvent, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Drawer } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { deleteConversation, useConversations } from "../api";
import { ConfirmationCard } from "../confirmation/ConfirmationCard";
import { SourceList } from "../sources/SourceList";
import { NavigationSuggestion } from "./NavigationSuggestion";
import { useAiChat } from "./useAiChat";
import "../ai.css";

/**
 * The assistant panel (spec 018 T012), opened from the shell's ``AiEntry`` slot on any page: streamed
 * answers in a polite live region, sources and caveats, proposed actions to confirm, page suggestions.
 * Answers are rendered as **text** (never HTML). When the assistant is unavailable the panel says so and
 * nothing else in the portal is affected.
 */
export interface AiPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  available: boolean;
  autoNavigate: boolean;
  context?: { route?: string; title?: string } | undefined;
}

export function AiPanel({ open, onOpenChange, available, autoNavigate, context }: AiPanelProps) {
  const t = useT();
  const chat = useAiChat(context);
  const conversations = useConversations(open && available);
  const [draft, setDraft] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft;
    setDraft("");
    void chat.send(text);
  };
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={t("ai:panel.title")}
      description={t("ai:panel.description")}
      closeLabel={t("ai:panel.close")}
      trigger={<span hidden />}
    >
      {!available ? (
        <FunctionalState state="unavailable" label={t("ai:panel.unavailable")} />
      ) : (
        <div className="ai-panel">
          <div className="ds-stack--row ai-panel__bar">
            <Button variant="secondary" onClick={chat.reset}>
              {t("ai:panel.newConversation")}
            </Button>
            {conversations.data?.length ? (
              <select
                aria-label={t("ai:panel.history")}
                value={chat.conversationId ?? ""}
                onChange={(event) => event.target.value && void chat.open(event.target.value)}
              >
                <option value="">{t("ai:panel.history")}</option>
                {conversations.data.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title || c.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            ) : null}
            {chat.conversationId ? (
              <Button
                variant="secondary"
                onClick={() => {
                  const id = chat.conversationId;
                  chat.reset();
                  if (id) void deleteConversation(id).then(() => conversations.refetch());
                }}
              >
                {t("ai:panel.delete")}
              </Button>
            ) : null}
          </div>
          <div className="ai-log" role="log" aria-live="polite" aria-busy={chat.busy}>
            {chat.messages.length === 0 ? <p className="ai-meta">{t("ai:panel.empty")}</p> : null}
            {chat.messages.map((message, index) => (
              <article
                // biome-ignore lint/suspicious/noArrayIndexKey: messages are append-only within a conversation
                key={index}
                className={`ai-message ai-message--${message.role}`}
                aria-label={message.role === "user" ? t("ai:panel.you") : t("ai:panel.assistant")}
              >
                {message.tools.length ? (
                  <p className="ai-meta">
                    {message.tools.map((tool) => t("ai:panel.toolCall", { tool })).join(" · ")}
                  </p>
                ) : null}
                <p className="ai-text">{message.content}</p>
                {message.streaming ? <p className="ai-meta">{t("ai:panel.thinking")}</p> : null}
                {message.error ? <p role="alert">{errorText(t, message.error)}</p> : null}
                {message.role === "assistant" && !message.streaming && !message.error ? (
                  <>
                    <SourceList
                      sources={message.sources}
                      caveats={message.caveats}
                      interpretation={message.interpretation && Boolean(message.content)}
                    />
                    <NavigationSuggestion
                      sources={message.sources}
                      autoNavigate={autoNavigate && index === chat.messages.length - 1}
                    />
                  </>
                ) : null}
                {message.pending.map((id) => (
                  <ConfirmationCard key={id} actionId={id} />
                ))}
              </article>
            ))}
          </div>
          {chat.error && !chat.messages.some((m) => m.error) ? (
            <p role="alert">{errorText(t, chat.error)}</p>
          ) : null}
          <form className="ai-form" onSubmit={submit}>
            <label className="visually-hidden" htmlFor="ai-input">
              {t("ai:panel.placeholder")}
            </label>
            <textarea
              id="ai-input"
              value={draft}
              maxLength={4000}
              rows={3}
              placeholder={t("ai:panel.placeholder")}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            {chat.busy ? (
              <Button type="button" variant="secondary" onClick={chat.stop}>
                {t("ai:panel.stop")}
              </Button>
            ) : (
              <Button type="submit" disabled={!draft.trim()}>
                {t("ai:panel.send")}
              </Button>
            )}
          </form>
        </div>
      )}
    </Drawer>
  );
}

function errorText(t: (id: string) => string, code: string): string {
  const known = ["ai.unavailable", "ai.rate_limited", "ai.budget_exceeded"];
  return t(known.includes(code) ? `ai:panel.error.${code}` : "ai:panel.error.generic");
}
