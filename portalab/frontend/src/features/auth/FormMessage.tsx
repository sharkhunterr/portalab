import { forwardRef } from "react";

/**
 * Form-level message. Errors use `role="alert"` (announced immediately) and receive focus so keyboard and
 * screen-reader users land on them; confirmations use `role="status"`. Never conveyed by color alone: the
 * text itself states the outcome.
 */
export interface FormMessageProps {
  kind: "error" | "success";
  children: string;
}

export const FormMessage = forwardRef<HTMLParagraphElement, FormMessageProps>(function FormMessage(
  { kind, children },
  ref,
) {
  return (
    <p
      ref={ref}
      tabIndex={-1}
      role={kind === "error" ? "alert" : "status"}
      className={`form-message form-message-${kind}`}
    >
      {children}
    </p>
  );
});
