import {
  Activity,
  AlertTriangle,
  Ban,
  Bell,
  Bolt,
  BookOpen,
  Calendar,
  ChartColumn,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  CircleDashed,
  Clock,
  Coins,
  Compass,
  Ellipsis,
  Film,
  Gamepad2,
  Gauge,
  Globe,
  GripVertical,
  Heart,
  Home,
  Image,
  Inbox,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  Lightbulb,
  Link,
  List,
  Lock,
  LogOut,
  type LucideIcon,
  Maximize2,
  Menu,
  MessageCircle,
  Minus,
  Moon,
  Newspaper,
  Palette,
  Plug,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings,
  Shield,
  ShoppingBag,
  Sparkles,
  Star,
  Sun,
  Target,
  Ticket,
  Trophy,
  User,
  Users,
  Wrench,
  X,
  Zap,
} from "lucide-react";

/**
 * ``Icon`` (spec 027 R15): declarations (navigation, widgets, sections, themes) reference icons by a
 * stable *name*, never a component — they stay data. Unknown names render a neutral dot. Icons are
 * decorative unless a ``label`` is given (then they are announced as an image).
 */
export const ICONS: Record<string, LucideIcon> = {
  activity: Activity,
  alert: AlertTriangle,
  warning: AlertTriangle,
  blocked: Ban,
  bell: Bell,
  bolt: Bolt,
  book: BookOpen,
  calendar: Calendar,
  chart: ChartColumn,
  check: Check,
  "chevron-down": ChevronDown,
  "chevron-left": ChevronLeft,
  "chevron-right": ChevronRight,
  clock: Clock,
  coins: Coins,
  compass: Compass,
  more: Ellipsis,
  film: Film,
  media: Film,
  game: Gamepad2,
  gauge: Gauge,
  globe: Globe,
  grip: GripVertical,
  heart: Heart,
  home: Home,
  image: Image,
  inbox: Inbox,
  key: KeyRound,
  dashboard: LayoutDashboard,
  lifebuoy: LifeBuoy,
  "life-buoy": LifeBuoy,
  lightbulb: Lightbulb,
  link: Link,
  list: List,
  lines: List,
  lock: Lock,
  logout: LogOut,
  maximize: Maximize2,
  menu: Menu,
  message: MessageCircle,
  minus: Minus,
  moon: Moon,
  newspaper: Newspaper,
  palette: Palette,
  plug: Plug,
  plus: Plus,
  sync: RefreshCw,
  spinner: CircleDashed,
  half: CircleDashed,
  search: Search,
  server: Server,
  settings: Settings,
  shield: Shield,
  shop: ShoppingBag,
  sparkles: Sparkles,
  star: Star,
  sun: Sun,
  target: Target,
  ticket: Ticket,
  trophy: Trophy,
  user: User,
  users: Users,
  wrench: Wrench,
  close: X,
  zap: Zap,
};

export interface IconProps {
  name: string | null | undefined;
  /** Accessible name; omit for decorative icons next to a visible label. */
  label?: string;
  size?: number;
  className?: string;
}

export function Icon({ name, label, size = 20, className }: IconProps) {
  const Component = (name && ICONS[name]) || Circle;
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const };
  return (
    <Component
      className={["ds-icon", className].filter(Boolean).join(" ")}
      width={size}
      height={size}
      strokeWidth={1.9}
      data-icon={name && ICONS[name] ? name : "unknown"}
      focusable="false"
      {...a11y}
    />
  );
}
