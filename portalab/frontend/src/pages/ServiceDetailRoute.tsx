import { useParams } from "react-router";
import { ServiceDetail } from "../features/services";

/** Service detail (existence-sensitive route: a missing or forbidden service shows the same state). */
export default function ServiceDetailRoute() {
  const { serviceId = "" } = useParams();
  return <ServiceDetail serviceId={serviceId} name={serviceId} />;
}
