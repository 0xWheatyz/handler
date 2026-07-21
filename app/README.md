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
| Agent detail | `src/screens/AgentDetailScreen.tsx` | Checkmark / Log segmented control, meta table, Answer / Pause / Kill |
| Answer | `src/screens/AnswerScreen.tsx` | Question, tappable quick replies, reply field + **Send & resume** |
| Spawn | `src/screens/SpawnScreen.tsx` | Project select, task field, two toggles, Spawn |
| Log | `src/screens/LogScreen.tsx` | All / handler / Errors filters over the global feed |
| Settings | `src/screens/SettingsScreen.tsx` | Server info, notification toggles, Sign out |

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
