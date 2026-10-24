import { useStrings } from "../../i18n/hooks/useStrings";

/** Privacy screens strings (spec 021 T036/T038), externalized for the i18n module (spec 026). */
export const privacyStrings = {
  centerTitle: "Privacy center",
  centerIntro: "What the portal holds about you, who can see it and how long it is kept.",
  dataClass: "Data",
  owner: "Kept by",
  classification: "Kind",
  visibility: "Visible to",
  retention: "Kept for",
  retentionDays: (days: number) => `${days} days`,
  retentionNone: "While your account exists",
  locked: "Set by the administrator for now; your own choice is kept and comes back afterwards.",
  levels: {
    public: "Everyone",
    community: "Portal members",
    leaderboard: "Leaderboards only",
    private: "Only me",
  },
  exportLink: "Download a copy of my data",
  deletionLink: "Delete my account",
  summary: "Who sees what",
  levelHints: {
    public: "visible to anyone",
    community: "visible to portal members",
    leaderboard: "only in leaderboards",
    private: "only you",
  },
  owners: {
    community: "Community",
    events: "Activity",
    media: "Media",
    identity: "Profile",
    gamification: "Progression",
    statistics: "Statistics",
    marketplace: "Shop",
    support: "Support",
  } as Record<string, string>,
  kinds: { activity: "Activity", history: "History", personal: "Personal" } as Record<string, string>,
  chooseVisibility: (datum: string) => `Who sees: ${datum}`,
  saved: "Saved.",
  yourData: "Your data",
  yourDataHint: "Take a copy of everything the portal holds about you, or leave for good.",
  policiesTitle: "Visibility overrides",
  noPolicies: "No active override.",
  policyFor: (who: string, datum: string) => `${datum} — ${who}`,
  everyone: "all members",
  removePolicy: "Remove the override",
  newPolicyTitle: "New override",
  datumField: "Data",
  modeField: "Rule",
  modes: {
    force_private: "Force private",
    force_visible: "Force visible",
    user_choice: "Follow the member's choice",
  },
  levelField: "Visible to",
  subjectField: "Member id (empty = everyone)",
  reasonField: "Reason",
  apply: "Apply",
  alreadyActive: "An override is already active for this data. Remove it first.",
  policiesDescription:
    "Force a datum private or visible for everyone or one member; their own choice is kept.",
  activePolicies: "Active overrides",
  auditDescription: "Every sensitive action, who did it and the outcome. Reading the log is itself audited.",
  auditEntries: "Entries",
  auditWhen: "When",
  auditActionColumn: "Action",
  auditActor: "Actor",
  auditDecision: "Decision",
  auditDetails: "Details",
  auditTitle: "Audit log",
  auditAction: "Action prefix",
  auditSearch: "Search",
  auditMore: "Older entries",
  auditExport: "Export (NDJSON)",
  auditEmpty: "No entry matches.",
  auditRedacted: (keys: string) => `Details hidden (${keys})`,
  genericError: "The change was refused. Check the values and try again.",
} as const;

/** Issue 201: the privacy texts in the member's language (``account:privacy.*``). */
export function usePrivacyStrings() {
  return useStrings(privacyStrings, "account:privacy", {
    retentionDays: ["days"],
    chooseVisibility: ["datum"],
    policyFor: ["who", "datum"],
    auditRedacted: ["keys"],
  });
}

export type LevelKey = keyof typeof privacyStrings.levels;
