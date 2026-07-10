/* Handler web UI — vanilla + Alpine.js, no build step.
 *
 * Classic (non-module) script: `function app()` below becomes a global that the
 * shell references via x-data="app()". Loaded with `defer` BEFORE alpine.min.js so
 * the global exists before Alpine evaluates the DOM.
 *
 * Security: every value from the API is rendered with Alpine `x-text` (textContent)
 * in index.html — never x-html — so agent-authored strings can't inject markup.
 */

const TOKEN_KEY = "handler_token";
const PROJECT_KEY = "handler_project";
const POLL_MS = 5000;
const LOG_LIMIT = 100;

/* Raised when the API rejects our token; callers re-prompt for it. */
class AuthError extends Error {}

function app() {
  return {
    // --- auth / shell ---
    token: null,
    tokenInput: "",
    showTokenModal: true,
    tokenError: "",

    // --- data ---
    projects: [],
    selectedProjectId: "",
    agents: [],
    selectedAgentName: null,
    checkmark: null,
    checkmarkMissing: false,
    log: [],
    logLimit: LOG_LIMIT,
    logOffset: 0,
    shared: { log: [], context: [] },

    // --- answer form ---
    answerText: "",
    answerBusy: false,
    answerMsg: "",
    answerError: false,

    // --- ui ---
    tab: "agents",
    lastError: "",
    _poll: null,

    get selectedAgent() {
      return this.agents.find((a) => a.name === this.selectedAgentName) || null;
    },

    init() {
      this.token = localStorage.getItem(TOKEN_KEY);
      if (this.token) {
        this.showTokenModal = false;
        this.start();
      } else {
        this.showTokenModal = true;
        this.$nextTick(() => this.$refs.tokenField?.focus());
      }
      // Pause polling when the tab is hidden; resume (with an immediate tick) on return.
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
          this._stopPolling();
        } else if (this.token) {
          this.tick();
          this._startPolling();
        }
      });
    },

    // --- token lifecycle ---
    saveToken() {
      const t = this.tokenInput.trim();
      if (!t) return;
      this.token = t;
      localStorage.setItem(TOKEN_KEY, t);
      this.tokenInput = "";
      this.tokenError = "";
      this.showTokenModal = false;
      this.start();
    },

    signOut() {
      this._stopPolling();
      this.token = null;
      localStorage.removeItem(TOKEN_KEY);
      this.projects = [];
      this.agents = [];
      this.selectedAgentName = null;
      this.checkmark = null;
      this.showTokenModal = true;
      this.$nextTick(() => this.$refs.tokenField?.focus());
    },

    _handle401() {
      this._stopPolling();
      this.token = null;
      localStorage.removeItem(TOKEN_KEY);
      this.tokenError = "Invalid token — please try again.";
      this.showTokenModal = true;
      this.$nextTick(() => this.$refs.tokenField?.focus());
    },

    // --- fetch wrapper ---
    async api(path, opts = {}) {
      const headers = { Authorization: `Bearer ${this.token}` };
      if (opts.body !== undefined) headers["Content-Type"] = "application/json";
      const res = await fetch(path, {
        method: opts.method || "GET",
        headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
      if (res.status === 401) {
        this._handle401();
        throw new AuthError("unauthorized");
      }
      if (!res.ok) {
        let detail = `${res.status}`;
        try {
          detail = (await res.json()).detail || detail;
        } catch (_) {}
        const err = new Error(detail);
        err.status = res.status;
        throw err;
      }
      if (res.status === 204) return null;
      return res.json();
    },

    // --- lifecycle ---
    async start() {
      await this.loadProjects();
      const saved = localStorage.getItem(PROJECT_KEY);
      if (saved && this.projects.some((p) => p.id === saved)) {
        await this.selectProject(saved);
      }
      this._startPolling();
    },

    _startPolling() {
      this._stopPolling();
      this._poll = setInterval(() => this.tick(), POLL_MS);
    },
    _stopPolling() {
      if (this._poll) {
        clearInterval(this._poll);
        this._poll = null;
      }
    },

    /* One poll cycle for whatever view is active. Swallows AuthError (already handled). */
    async tick() {
      try {
        if (this.tab === "shared") {
          await this.loadShared();
          return;
        }
        if (this.selectedProjectId) await this.loadAgents();
        if (this.selectedAgentName) {
          await this.loadCheckmark();
          await this.loadLog();
        }
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },

    refresh() {
      this.tick();
    },

    // --- projects ---
    async loadProjects() {
      try {
        this.projects = await this.api("/projects");
        this.lastError = "";
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },

    async selectProject(id) {
      this.selectedProjectId = id;
      localStorage.setItem(PROJECT_KEY, id);
      this.selectedAgentName = null;
      this.checkmark = null;
      this.log = [];
      this.logOffset = 0;
      await this.loadAgents();
    },

    // --- agents ---
    async loadAgents() {
      const p = this.selectedProjectId;
      if (!p) return;
      const agents = await this.api(`/projects/${encodeURIComponent(p)}/agents`);
      this.agents = agents;
      this.lastError = "";
    },

    async selectAgent(name) {
      this.selectedAgentName = name;
      this.answerText = "";
      this.answerMsg = "";
      this.answerError = false;
      this.logOffset = 0;
      await this.loadCheckmark();
      await this.loadLog();
    },

    _agentPath() {
      return `/projects/${encodeURIComponent(this.selectedProjectId)}/agents/${encodeURIComponent(this.selectedAgentName)}`;
    },

    async loadCheckmark() {
      try {
        this.checkmark = await this.api(`${this._agentPath()}/checkmark`);
        this.checkmarkMissing = false;
      } catch (e) {
        if (e instanceof AuthError) return;
        if (e.status === 404) {
          this.checkmark = null;
          this.checkmarkMissing = true;
        } else {
          this.lastError = e.message;
        }
      }
    },

    async loadLog() {
      try {
        this.log = await this.api(`${this._agentPath()}/log?limit=${this.logLimit}&offset=${this.logOffset}`);
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },

    pagePrev() {
      if (this.logOffset === 0) return;
      this.logOffset = Math.max(0, this.logOffset - this.logLimit);
      this.loadLog();
    },
    pageNext() {
      if (this.log.length < this.logLimit) return;
      this.logOffset += this.logLimit;
      this.loadLog();
    },

    // --- answer / resume ---
    async submitAnswer(resume) {
      const text = this.answerText.trim();
      if (!text) return;
      this.answerBusy = true;
      this.answerMsg = "";
      this.answerError = false;
      try {
        await this.api(`${this._agentPath()}/answer`, { method: "POST", body: { answer: text } });
        if (resume) {
          const r = await this.api(`${this._agentPath()}/resume`, { method: "POST", body: { answer: text } });
          if (r.resumed) {
            this.answerMsg = "Answered and resumed.";
            this.answerText = "";
            await this.tick(); // flip the badge to working without waiting a full interval
          } else {
            this.answerError = true;
            this.answerMsg = `Answer saved, but resume failed: ${r.detail || "unknown error"}`;
            await this.loadCheckmark();
            await this.loadLog();
          }
        } else {
          this.answerMsg = "Answer saved (agent still paused).";
          this.answerText = "";
          await this.loadCheckmark();
          await this.loadLog();
        }
      } catch (e) {
        if (e instanceof AuthError) return;
        this.answerError = true;
        this.answerMsg = e.message;
      } finally {
        this.answerBusy = false;
      }
    },

    // --- shared tab ---
    switchToShared() {
      this.tab = "shared";
      this.loadShared();
    },

    async loadShared() {
      try {
        const [log, context] = await Promise.all([
          this.api("/shared/log"),
          this.api("/shared/context"),
        ]);
        this.shared = { log, context };
        this.lastError = "";
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },

    // --- rendering helpers ---
    badgeClass(kind, value) {
      const v = value == null ? "unknown" : String(value);
      return `badge-${kind}-${v.replace(/[^a-z0-9_]/gi, "")}`;
    },

    fmt(ts) {
      if (!ts) return "";
      const d = new Date(ts);
      if (isNaN(d)) return String(ts);
      return d.toLocaleString();
    },
  };
}
