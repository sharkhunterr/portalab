/** Every widget the dashboards draw, registered once — the members' dashboard and its administrator's editor
 * (issue 250) show the same ones. */
import "../summary/SinceLastLoginCard";
import "./tiles";
import "./layout";
import "./builtin";
import "./media";
import "./calendar";
import "../../gamification/widget";
import "../../community/widget";
import "../../marketplace/widget";
import "../../support/incidents/widget";
import "../../support/tickets/widget";
import "../../campaigns/widget";
import "../../news/MyFeedWidget"; // issue 315: « Mon fil »
import "./discover";
import "./downloads";
import "./leaving";
import "./service-status";
import "../../services/HostWidgets";
import "./pack/PackWidget"; // 028: packs' widgets
import "./skins"; // 027 (#31): last — the other looks wrap the widgets registered above
