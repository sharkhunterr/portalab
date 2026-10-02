import { useState } from "react";
import { AnnounceProvider, useAnnounce } from "../../../design-system/a11y/Announce";
import { PreferencesProvider } from "../../../design-system/a11y/PreferencesProvider";
import { Button, Link } from "../../../design-system/components/Button";
import {
  Avatar,
  Badge,
  Card,
  EntityCard,
  Panel,
  Progress,
  Timeline,
} from "../../../design-system/components/Content";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Container, Grid, Stack, Table } from "../../../design-system/components/Layout";
import { NotificationArea, useNotify } from "../../../design-system/components/Notification";
import { Dialog, Drawer, Menu, Popover, Tooltip } from "../../../design-system/components/Overlays";
import { PolicyField } from "../../../design-system/components/PolicyField";
import { Tabs } from "../../../design-system/components/Tabs";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { FUNCTIONAL_STATES } from "../../../design-system/state/stateMap";
import { BUILTIN_THEMES } from "../../../design-system/themes/builtin";
import { ThemeProvider } from "../../../design-system/themes/ThemeProvider";

/**
 * Dev-only component gallery (spec 022 T039): every component and every functional state, under each
 * built-in theme, with density/contrast/motion toggles. Served at ``/dev/gallery`` in development only;
 * the accessibility CI job runs axe and keyboard journeys against it.
 */
function Demos() {
  const notify = useNotify();
  const announce = useAnnounce();
  const [menuResult, setMenuResult] = useState("");
  return (
    <Stack>
      <section aria-labelledby="g-states">
        <h2 id="g-states">Functional states</h2>
        <Grid>
          {FUNCTIONAL_STATES.map((state) => (
            <FunctionalState
              key={state}
              state={state}
              detail="Media library"
              onRetry={() => announce(`Retry ${state}`)}
            />
          ))}
        </Grid>
      </section>
      <section aria-labelledby="g-actions">
        <h2 id="g-actions">Actions</h2>
        <Stack row>
          <Button onClick={() => notify({ severity: "info", title: "Saved" })}>Primary action</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="danger">Delete</Button>
          <Link href="#g-forms">Jump to forms</Link>
          <Tooltip content="Opens the help panel">
            <Button variant="secondary">Help</Button>
          </Tooltip>
          <Menu
            label="More actions"
            trigger={<Button variant="secondary">More</Button>}
            items={[
              { key: "a", label: "Archive", onSelect: () => setMenuResult("Archived") },
              { key: "b", label: "Share", onSelect: () => setMenuResult("Shared") },
            ]}
          />
          <Popover label="Details" trigger={<Button variant="secondary">Details</Button>}>
            <p>Popover content</p>
          </Popover>
          <Dialog title="Confirm" trigger={<Button>Open dialog</Button>}>
            <p>Dialog body.</p>
          </Dialog>
          <Drawer title="Filters" trigger={<Button variant="secondary">Open drawer</Button>}>
            <p>Drawer body.</p>
          </Drawer>
        </Stack>
        {menuResult ? <p role="status">{menuResult}</p> : null}
      </section>
      <section aria-labelledby="g-forms">
        <h2 id="g-forms">Forms</h2>
        <TextField label="Display name" hint="Visible to members" autoComplete="nickname" />
        <TextField label="Password" type="password" autoComplete="current-password" error="Too short" />
        <SelectField label="Language" defaultValue="en">
          <option value="en">English</option>
          <option value="fr">Français</option>
        </SelectField>
        <CheckboxField label="Subscribe" />
        <PolicyField id="g-policy" state="locked" retainedValue="Dark">
          {({ disabled, describedBy }) => (
            <SelectField
              label="Theme (policy)"
              disabled={disabled}
              aria-describedby={describedBy}
              defaultValue="dark"
            >
              <option value="dark">Dark</option>
            </SelectField>
          )}
        </PolicyField>
      </section>
      <section aria-labelledby="g-content">
        <h2 id="g-content">Content</h2>
        <Tabs
          label="Sections"
          items={[
            { value: "a", label: "Overview", content: <p>Overview panel</p> },
            { value: "b", label: "History", content: <p>History panel</p> },
          ]}
        />
        <Grid>
          <Card title="Card">
            <p>Card body</p>
            <Badge tone="available">Online</Badge>
          </Card>
          <Panel title="Panel">
            <Progress label="Sync progress" value={40} />
            <Progress label="Loading" value={null} />
          </Panel>
          <EntityCard kind="service" title="Media server" subtitle="Plex" state="maintenance" />
          <EntityCard kind="user" title="Alex Martin" meta={<Avatar name="Alex Martin" />} />
        </Grid>
        <Timeline
          label="Recent changes"
          entries={[
            { id: "1", at: "2026-10-01T10:00:00Z", title: "Synced" },
            { id: "2", at: "2026-10-01T11:00:00Z", title: "Degraded" },
          ]}
        />
        <Table
          caption="Services"
          rowKey={(row) => row.name}
          rows={[
            { name: "Media", state: "available" as const },
            { name: "Books", state: "error" as const },
          ]}
          columns={[
            { key: "name", header: "Service", rowHeader: true, render: (row) => row.name },
            { key: "state", header: "State", render: (row) => <FunctionalState state={row.state} /> },
          ]}
        />
      </section>
    </Stack>
  );
}

export function Gallery() {
  const [theme, setTheme] = useState("light");
  const [density, setDensity] = useState<"compact" | "comfortable" | "spacious">("comfortable");
  const [contrast, setContrast] = useState<"default" | "high">("default");
  return (
    <PreferencesProvider key={`${theme}-${density}-${contrast}`} initial={{ theme, density, contrast }}>
      <ThemeProvider>
        <AnnounceProvider>
          <NotificationArea>
            <Container>
              <main id="main-content">
                <h1>Component gallery</h1>
                <Stack row>
                  <SelectField label="Gallery theme" value={theme} onChange={(e) => setTheme(e.target.value)}>
                    {BUILTIN_THEMES.map((t) => (
                      <option key={t.key} value={t.key}>
                        {t.name}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="Gallery density"
                    value={density}
                    onChange={(e) => setDensity(e.target.value as typeof density)}
                  >
                    <option value="compact">Compact</option>
                    <option value="comfortable">Comfortable</option>
                    <option value="spacious">Spacious</option>
                  </SelectField>
                  <CheckboxField
                    label="Gallery high contrast"
                    checked={contrast === "high"}
                    onChange={(e) => setContrast(e.target.checked ? "high" : "default")}
                  />
                </Stack>
                <Demos />
              </main>
            </Container>
          </NotificationArea>
        </AnnounceProvider>
      </ThemeProvider>
    </PreferencesProvider>
  );
}
