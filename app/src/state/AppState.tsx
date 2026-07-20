import React, { createContext, useContext, useMemo, useState } from "react";

/**
 * Central prototype state, ported 1:1 from the DC script's
 * `state` + `renderVals()` in project/Handler Mobile.dc.html (turn 2a).
 *
 * The prototype navigates by swapping a single `screen` value rather than a
 * stack, and answering agt-7a1d flips it Waiting -> Running everywhere. That
 * cross-screen behavior is exactly why this lives in one shared store.
 */

export type Screen =
  | "fleet"
  | "detail"
  | "answer"
  | "spawn"
  | "log"
  | "settings";

export type DetailTab = "state" | "log";
export type LogFilter = "all" | "handler" | "errors";
export type BadgeTone = "neutral" | "positive" | "warning" | "danger";

const ANSWERED_STATE =
  "Answer received: keep the JSON store as a read-only fallback for one release. Deprecating writes now; removal ticket filed for next cycle.";
const WAITING_STATE =
  "Schema written, migrations pass. Blocked on the legacy JSON store — drop it or keep as read fallback? Holding before deleting store/json.rs.";

interface AppStateValue {
  screen: Screen;
  detailTab: DetailTab;
  quickPick: number | null;
  logFilter: LogFilter;
  answered: boolean;
  swEdits: boolean;
  swTests: boolean;
  swPushWait: boolean;
  swPushFail: boolean;

  // Derived (mirrors renderVals()).
  notAnswered: boolean;
  agentTone: BadgeTone;
  agentStatus: string;
  agentStateText: string;

  go: (screen: Screen) => void;
  setDetailTab: (tab: DetailTab) => void;
  setQuickPick: (i: number) => void;
  setLogFilter: (f: LogFilter) => void;
  sendResume: () => void;
  spawnGo: () => void;
  setSwEdits: (v: boolean) => void;
  setSwTests: (v: boolean) => void;
  setSwPushWait: (v: boolean) => void;
  setSwPushFail: (v: boolean) => void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [screen, setScreen] = useState<Screen>("fleet");
  const [detailTab, setDetailTab] = useState<DetailTab>("state");
  const [quickPick, setQuickPickState] = useState<number | null>(null);
  const [logFilter, setLogFilter] = useState<LogFilter>("all");
  const [answered, setAnswered] = useState(false);
  const [swEdits, setSwEdits] = useState(false);
  const [swTests, setSwTests] = useState(true);
  const [swPushWait, setSwPushWait] = useState(true);
  const [swPushFail, setSwPushFail] = useState(true);

  const value = useMemo<AppStateValue>(
    () => ({
      screen,
      detailTab,
      quickPick,
      logFilter,
      answered,
      swEdits,
      swTests,
      swPushWait,
      swPushFail,

      notAnswered: !answered,
      agentTone: answered ? "positive" : "warning",
      agentStatus: answered ? "Running" : "Waiting",
      agentStateText: answered ? ANSWERED_STATE : WAITING_STATE,

      go: setScreen,
      setDetailTab,
      setQuickPick: setQuickPickState,
      setLogFilter,
      sendResume: () => {
        setAnswered(true);
        setDetailTab("state");
        setScreen("detail");
      },
      spawnGo: () => setScreen("fleet"),
      setSwEdits,
      setSwTests,
      setSwPushWait,
      setSwPushFail,
    }),
    [
      screen,
      detailTab,
      quickPick,
      logFilter,
      answered,
      swEdits,
      swTests,
      swPushWait,
      swPushFail,
    ]
  );

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}
