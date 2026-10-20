import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { deleteConversation, useConversations } from "../api";
import { ConfirmationCard } from "../confirmation/ConfirmationCard";
import { pageContext, pageLabel } from "../pageContext";
import { SourceList } from "../sources/SourceList";
import { AnswerText } from "./AnswerText";
import { NavigationSuggestion } from "./NavigationSuggestion";
import { useAiChat } from "./useAiChat";
import "../ai.css";

/**
 * The assistant (spec 018 T012; issue 171: a window of its own, reached from anywhere): a conversation in
 * bubbles — the member's questions on one side, the streamed answers on the other, laid out (lists, bold,
 * the portal's pages as links) with their numbered sources, proposed actions to confirm and page
 * suggestions; ideas to start with; the past conversations beside it. Centred on a computer, the whole
 * screen on a phone. When the assistant is unavailable it says so and nothing else is affected.
 */
export interface AiPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  available: boolean;
  autoNavigate: boolean;
  context?: { route?: string; title?: string; question?: string; asked?: number } | undefined;
  /** issue 171: the assistant's name (the administrators'), else « Assistant » */
  name?: string | undefined;
  /** issue 171: today's allowance and what the member used of it (tokens) */
  quota?: { budget: number; used: number } | undefined;
}

const IDEAS = ["services", "tickets", "news", "media"] as const;

export function AiPanel({ open, onOpenChange, available, autoNavigate, context, name, quota }: AiPanelProps) {
  const t = useT();
  const format = useFormat();
  // issue 171: the page the member is on, in a few words (never more than the route and one line)
  const page = useMemo(() => (open ? pageContext(context?.route) : undefined), [open, context?.route]);
  const where = useMemo(() => (open ? pageLabel(context?.route) : undefined), [open, context?.route]);
  const chat = useAiChat(page);
  const conversations = useConversations(open && available);
  const [draft, setDraft] = useState("");
  const client = useQueryClient();
  // issue 171: the allowance shown is refreshed once an answer is done
  // biome-ignore lint/correctness/useExhaustiveDependencies: on each answer's end only
  useEffect(() => {
    if (!chat.busy) void client.invalidateQueries({ queryKey: ["ai", "status"] });
  }, [chat.busy]);
  const left = quota ? Math.max(0, Math.round(100 - (quota.used / quota.budget) * 100)) : undefined;
  const [history, setHistory] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  // issue 171: opened with a question (the search bar, a page's « ask the assistant »): asked at once
  const asked = context?.asked;
  const answered = useRef<number | undefined>(undefined);
  // biome-ignore lint/correctness/useExhaustiveDependencies: once per question asked
  useEffect(() => {
    if (!open || !available || !asked || !context?.question || answered.current === asked) return;
    answered.current = asked;
    setHistory(false);
    void chat.send(context.question, { fresh: true });
  }, [asked, open, available]);
  // the newest words in view while they arrive
  const last = chat.messages[chat.messages.length - 1];
  // biome-ignore lint/correctness/useExhaustiveDependencies: follows the answer as it grows
  useEffect(() => {
    const node = log.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [chat.messages.length, last?.content, last?.streaming]);

  const ask = (text: string) => {
    if (!text.trim() || chat.busy) return;
    setDraft("");
    setHistory(false);
    void chat.send(text);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(draft);
  };
  const fresh = () => {
    chat.reset();
    setHistory(false);
    window.setTimeout(() => input.current?.focus(), 0);
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ai-overlay" />
        <DialogPrimitive.Content
          className="ai-modal"
          data-history={history || undefined}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            input.current?.focus();
          }}
        >
          <header className="ai-modal__head">
            <span className="ai-modal__mark" aria-hidden="true">
              <Icon name="sparkles" size={20} />
            </span>
            <div className="ai-modal__titles">
              <DialogPrimitive.Title className="ai-modal__title">
                {name || t("ai:panel.title")}
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="ai-modal__description">
                {t("ai:panel.description")}
              </DialogPrimitive.Description>
            </div>
            <div className="ai-modal__actions">
              {available ? (
                <>
                  <button
                    type="button"
                    className="ai-icon-button"
                    aria-pressed={history}
                    aria-label={t("ai:panel.history")}
                    title={t("ai:panel.history")}
                    onClick={() => setHistory(!history)}
                  >
                    <Icon name="clock" size={18} />
                  </button>
                  <button
                    type="button"
                    className="ai-icon-button"
                    aria-label={t("ai:panel.newConversation")}
                    title={t("ai:panel.newConversation")}
                    onClick={fresh}
                  >
                    <Icon name="plus" size={18} />
                  </button>
                </>
              ) : null}
              <DialogPrimitive.Close asChild>
                <button
                  type="button"
                  className="ai-icon-button"
                  aria-label={t("ai:panel.close")}
                  title={t("ai:panel.close")}
                >
                  <Icon name="close" size={18} />
                </button>
              </DialogPrimitive.Close>
            </div>
          </header>

          {!available ? (
            <div className="ai-modal__body">
              <FunctionalState state="unavailable" label={t("ai:panel.unavailable")} />
            </div>
          ) : (
            <div className="ai-modal__body">
              {history ? (
                <nav className="ai-history" aria-label={t("ai:panel.history")}>
                  {conversations.data?.length ? (
                    <ul>
                      {conversations.data.map((c) => (
                        <li key={c.id} data-current={c.id === chat.conversationId || undefined}>
                          <button
                            type="button"
                            onClick={() => {
                              setHistory(false);
                              void chat.open(c.id);
                            }}
                          >
                            <span className="ai-history__title">{c.title || t("ai:panel.untitled")}</span>
                            <span className="ai-history__date">{format.dateTime(c.updated_at)}</span>
                          </button>
                          <button
                            type="button"
                            className="ai-icon-button"
                            aria-label={t("ai:panel.delete")}
                            title={t("ai:panel.delete")}
                            onClick={() => {
                              if (c.id === chat.conversationId) chat.reset();
                              void deleteConversation(c.id).then(() => conversations.refetch());
                            }}
                          >
                            <Icon name="trash" size={16} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="ai-meta">{t("ai:panel.empty")}</p>
                  )}
                </nav>
              ) : null}

              {where ? (
                // issue 171: what « this » means here — the page the member asks from
                <p className="ai-context">
                  <Icon name="map-pin" size={14} /> {t("ai:panel.context", { page: where })}
                </p>
              ) : null}
              <div className="ai-log" ref={log} role="log" aria-live="polite" aria-busy={chat.busy}>
                {chat.messages.length === 0 ? (
                  <div className="ai-welcome">
                    <span className="ai-welcome__mark" aria-hidden="true">
                      <Icon name="sparkles" size={28} />
                    </span>
                    <p className="ai-welcome__hello">{t("ai:panel.hello")}</p>
                    <div className="ai-ideas">
                      {IDEAS.map((idea) => (
                        <button key={idea} type="button" onClick={() => ask(t(`ai:panel.idea.${idea}`))}>
                          {t(`ai:panel.idea.${idea}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                {chat.messages.map((message, index) => (
                  <article
                    // biome-ignore lint/suspicious/noArrayIndexKey: messages are append-only within a conversation
                    key={index}
                    className="ai-bubble"
                    data-role={message.role}
                    aria-label={message.role === "user" ? t("ai:panel.you") : t("ai:panel.assistant")}
                  >
                    {message.role === "user" ? (
                      <>
                        <p className="ai-bubble__text">{message.content}</p>
                        <MessageActions
                          text={message.content}
                          resend={chat.busy ? undefined : () => ask(message.content)}
                          resendLabel={t("ai:panel.resend")}
                        />
                      </>
                    ) : (
                      <>
                        {message.content ? (
                          <AnswerText text={message.content} sources={message.sources} />
                        ) : null}
                        {message.streaming ? (
                          <p className="ai-typing">
                            <span className="ai-typing__dots" aria-hidden="true">
                              <span />
                              <span />
                              <span />
                            </span>
                            {message.tools.length ? t("ai:panel.lookingUp") : t("ai:panel.thinking")}
                          </p>
                        ) : null}
                        {message.error ? (
                          <p className="ai-bubble__error" role="alert">
                            {errorText(t, message.error)}
                          </p>
                        ) : null}
                        {!message.streaming && !message.error ? (
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
                        {!message.streaming && message.content ? (
                          <MessageActions
                            text={message.content}
                            resend={
                              chat.busy || !questionBefore(chat.messages, index)
                                ? undefined
                                : () => ask(questionBefore(chat.messages, index) ?? "")
                            }
                            resendLabel={t("ai:panel.retry")}
                          />
                        ) : null}
                      </>
                    )}
                  </article>
                ))}
                {chat.error && !chat.messages.some((m) => m.error) ? (
                  <p className="ai-bubble__error" role="alert">
                    {errorText(t, chat.error)}
                  </p>
                ) : null}
              </div>

              {left !== undefined ? (
                <p className="ai-quota" data-low={left <= 15 || undefined}>
                  <span className="ai-quota__bar" aria-hidden="true">
                    <span style={{ inlineSize: `${left}%` }} />
                  </span>
                  {t("ai:panel.quota", { percent: left })}
                </p>
              ) : null}
              <form className="ai-composer" onSubmit={submit}>
                <label className="visually-hidden" htmlFor="ai-input">
                  {t("ai:panel.placeholder")}
                </label>
                <textarea
                  id="ai-input"
                  ref={input}
                  value={draft}
                  maxLength={4000}
                  rows={1}
                  placeholder={t("ai:panel.placeholder")}
                  onChange={(event) => {
                    setDraft(event.target.value);
                    const node = event.currentTarget;
                    node.style.blockSize = "auto";
                    node.style.blockSize = `${Math.min(node.scrollHeight, 160)}px`;
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                {chat.busy ? (
                  <button
                    type="button"
                    className="ai-send"
                    data-stop=""
                    aria-label={t("ai:panel.stop")}
                    title={t("ai:panel.stop")}
                    onClick={chat.stop}
                  >
                    <Icon name="close" size={18} />
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="ai-send"
                    disabled={!draft.trim()}
                    aria-label={t("ai:panel.send")}
                    title={t("ai:panel.send")}
                  >
                    <Icon name="send" size={18} />
                  </button>
                )}
              </form>
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** The member's question an answer replied to (to ask it again). */
function questionBefore(messages: { role: string; content: string }[], index: number): string | undefined {
  for (let at = index - 1; at >= 0; at -= 1) {
    const message = messages[at];
    if (message?.role === "user") return message.content;
  }
  return undefined;
}

/** Issue 171 — under a message: copy it, send it again (a question) or ask again (an answer). */
function MessageActions({
  text,
  resend,
  resendLabel,
}: {
  text: string;
  resend: (() => void) | undefined;
  resendLabel: string;
}) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    const plain = text.replace(/\s*\[\d{1,2}\]/g, ""); // without the source numbers
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(plain);
      else {
        // an older browser: the selection's copy
        const area = document.createElement("textarea");
        area.value = plain;
        area.setAttribute("readonly", "");
        area.style.position = "absolute";
        area.style.insetInlineStart = "-9999px";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="ai-actions">
      <button
        type="button"
        className="ai-action"
        aria-label={copied ? t("ai:panel.copied") : t("ai:panel.copy")}
        title={copied ? t("ai:panel.copied") : t("ai:panel.copy")}
        onClick={() => void copy()}
      >
        <Icon name={copied ? "check" : "copy"} size={14} />
        {copied ? <span>{t("ai:panel.copied")}</span> : null}
      </button>
      {resend ? (
        <button
          type="button"
          className="ai-action"
          aria-label={resendLabel}
          title={resendLabel}
          onClick={resend}
        >
          <Icon name="retry" size={14} />
        </button>
      ) : null}
    </div>
  );
}

function errorText(t: (id: string) => string, code: string): string {
  const known = ["ai.unavailable", "ai.rate_limited", "ai.budget_exceeded"];
  return t(known.includes(code) ? `ai:panel.error.${code}` : "ai:panel.error.generic");
}
