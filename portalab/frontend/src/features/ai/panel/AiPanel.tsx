import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { deleteConversation, useConversations } from "../api";
import { ConfirmationCard } from "../confirmation/ConfirmationCard";
import { pageContext } from "../pageContext";
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
}

const IDEAS = ["services", "tickets", "news", "media"] as const;

export function AiPanel({ open, onOpenChange, available, autoNavigate, context }: AiPanelProps) {
  const t = useT();
  const format = useFormat();
  // issue 171: the page the member is on, in a few words (never more than the route and one line)
  const page = useMemo(() => (open ? pageContext(context?.route) : undefined), [open, context?.route]);
  const chat = useAiChat(page);
  const conversations = useConversations(open && available);
  const [draft, setDraft] = useState("");
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
              <DialogPrimitive.Title className="ai-modal__title">{t("ai:panel.title")}</DialogPrimitive.Title>
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
                      <p className="ai-bubble__text">{message.content}</p>
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

function errorText(t: (id: string) => string, code: string): string {
  const known = ["ai.unavailable", "ai.rate_limited", "ai.budget_exceeded"];
  return t(known.includes(code) ? `ai:panel.error.${code}` : "ai:panel.error.generic");
}
