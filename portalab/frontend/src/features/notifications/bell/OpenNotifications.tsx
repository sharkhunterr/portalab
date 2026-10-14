import { useEffect } from "react";
import { useNavigate } from "react-router";
import { OPEN_EVENT } from "./NotificationSlot";

/** ``/notifications``: back to where one came from (or home), the panel open over it. */
export function OpenNotifications() {
  const navigate = useNavigate();
  useEffect(() => {
    const came = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (came > 0) navigate(-1);
    else navigate("/", { replace: true });
    // once the page underneath is back
    const timer = window.setTimeout(() => window.dispatchEvent(new Event(OPEN_EVENT)), 0);
    return () => window.clearTimeout(timer);
  }, [navigate]);
  return null;
}

export default OpenNotifications;
