# Handler — mobile app

A remote control for [Handler](https://github.com/0xWheatyz/handler): run many
Claude Code agents across many projects, each isolated, each leaving a
checkmark (current state) and an entry in the global log.

This is the **React Native + Expo (iOS)** implementation of the
`Handler Mobile.dc.html` design (turn `2a`, the version the user committed to:
*"Commit to 1a, wire-up the real screens"*). It reproduces the interactive
prototype as a real app — six wired screens with the exact state logic from
the design.

## Run it

```bash
cd app
npm install
npm run ios      # opens the iOS simulator (requires Xcode)
# or: npm start   then scan the QR code with Expo Go on a device
```

## Screens

| Screen | File | What it does |
| --- | --- | --- |
| Fleet (home) | `src/screens/FleetScreen.tsx` | Stat cards, "Waiting on you" list → Answer, "Recent checkmarks" → detail |
| Agent detail | `src/screens/AgentDetailScreen.tsx` | Checkmark / Events / Log segmented control, live headless run event stream, meta table (incl. model backend + worker), Answer / Kill |
| Answer | `src/screens/AnswerScreen.tsx` | Question, tappable quick replies, reply field + **Send & resume** |
| Spawn | `src/screens/SpawnScreen.tsx` | Project select, model backend select, task field, Spawn |
| Schedules | `src/screens/SchedulesScreen.tsx` | Recurring agent spawns: list, create (interval / role / model), pause, delete |
| Memory | `src/screens/MemoryScreen.tsx` | The agent-memory note graph: kind filters, expandable notes, note authoring + deletion |
| Log | `src/screens/LogScreen.tsx` | All / per-project / Errors filters over the global feed |
| Settings | `src/screens/SettingsScreen.tsx` | Server info, Manage + Account entries, notification toggles, Sign out |
| Connect | `src/screens/ConnectScreen.tsx` | Email sign-in (`/auth/login`), first-run admin setup, forgot-password, API-token fallback |

### Management screens (Settings → Manage)

The full admin surface — everything the web dashboard can do, under
`src/screens/manage/`:

| Screen | What it does |
| --- | --- |
| Models | Model-backend CRUD: base URL, model ids, claude/pi harness, write-only API keys (set/clear), enable toggles |
| Skills | Create / toggle / delete managed skills, read SKILL.md, install-from-prompt via the command queue |
| Connectors | stdio / http / sse MCP servers with args, env, and header entry |
| Plugins | Marketplace plugins pinned to their repo |
| Permissions | Default permission mode + allow/deny/ask rules over the read-only env baseline |
| Claude login | Drive the worker's `claude /login` (authorize in browser, paste the code back) |
| Activity | The control-command queue: status filters, worker attribution, result/error detail, 5s auto-refresh |
| Repositories | Register repos (git-server or manual mode, optional mise-init bootstrap), sync, delete |
| Git servers | Forge hosts: encrypted tokens, generated deploy keys (public half copyable) |
| Approvals | Record operator approve / reject verdicts per project + branch |
| Shared context | Browse and set the cross-agent key/value store |
| Users | Invite (shareable links), promote / disable, mint reset links, delete |
| Account | Signed-in identity, change password, sign out (revokes the session server-side) |

The prototype navigates by swapping a single `screen` value (with working back
/ close controls) rather than a native stack, mirroring the design. Answering
`agt-7a1d` flips it **Waiting → Running** everywhere and clears it from the
Fleet waiting list — that cross-screen behavior lives in one shared store
(`src/state/AppState.tsx`, a direct port of the design's `renderVals()`).

## Design system

The Leeworks tokens (`project/_ds/.../tokens/*.css`) are ported to typed RN
values in `src/theme/tokens.ts`; the components used by these screens
(`Button`, `Badge`, `Icon`, `Switch`, `Select`, `Input`, segmented control,
chip) are reimplemented in `src/components/` from the design-system bundle.

- **Fonts:** Outfit (display), Figtree (body), Spline Sans Mono (data) via
  `@expo-google-fonts/*`.
- **Colors:** the warm-neutral ink ramp + muted status colors, light and dark.

## Intentional deviations from the HTML prototype

The prototype drew a phone frame to make an HTML mock look like a device. A
real iOS app *is* the device, so:

- The fake status bar (`9:41`, signal, battery) and the home-indicator pill are
  dropped — the OS draws those. Screens use safe-area insets and
  `expo-status-bar` instead.
- **Dark mode** was a design-time prop; here it follows the system appearance
  (`useColorScheme`, `userInterfaceStyle: "automatic"`).
- The `Select` uses a bottom-sheet picker (native `<select>` has no
  cross-platform styling in RN) — same field, real picking behavior.

All copy, spacing, colors, and interactions otherwise match the `2a` design.
