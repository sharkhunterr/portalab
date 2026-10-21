import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { WidgetHeaderAction, WidgetHeaderLink } from "../../dashboard/frame/actions";
import { ListTemplate } from "../../dashboard/templates/Templates";
import { registerWidgetComponent, type WidgetProps } from "../../dashboard/widgets/registry";
import { NewTicketForm } from "./NewTicket";
import "../support.css";

/**
 * « My tickets » (016; 027 #25): my open tickets, and « new ticket » in the widget's header — the form in a
 * dialog, without leaving the dashboard; the new ticket shows in the list at once, with a link to it.
 */
const FORM = "dashboard-new-ticket";

function MyTicketsWidget(props: WidgetProps) {
  const t = useT();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<string | null>(null);
  const items = ((props.payload.data ?? {}) as { items?: unknown[] }).items ?? [];
  return (
    <>
      <WidgetHeaderAction>
        <Dialog
          size="lg"
          title={t("support:new.title")}
          closeLabel={t("support:widget.my_tickets.close")}
          open={open}
          onOpenChange={setOpen}
          footer={
            <Button type="submit" form={FORM}>
              {t("support:new.submit")}
            </Button>
          }
          trigger={
            <button type="button" className="widget-frame__action">
              <Icon name="plus" size={12} />
              {t("support:widget.my_tickets.new")}
            </button>
          }
        >
          <NewTicketForm
            formId={FORM}
            onCreated={(ticket) => {
              setOpen(false);
              setCreated(ticket.id);
              void client.invalidateQueries({ queryKey: ["widget", "support.my_tickets"] });
            }}
          />
        </Dialog>
      </WidgetHeaderAction>
      {created ? (
        <p className="widget-tickets__created" role="status">
          <Icon name="check" size={14} />
          {t("support:widget.my_tickets.created")}{" "}
          <Link to={`/support/tickets/${created}`}>{t("support:widget.my_tickets.open")}</Link>
        </p>
      ) : null}
      <WidgetHeaderLink to="/support" label={t("support:widget.my_tickets.all")} />
      {items.length ? (
        <div className="widget-carousel">
          <ListTemplate {...props} />
        </div>
      ) : (
        <p className="widget-empty" data-state="no-data">
          <Icon name="lifebuoy" size={28} />
          <span>{t("support:widget.my_tickets.none")}</span>
        </p>
      )}
    </>
  );
}

registerWidgetComponent("support.my_tickets", MyTicketsWidget);
