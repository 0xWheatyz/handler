/* Handler web UI — vanilla + Alpine.js, no build step.
 *
 * Classic (non-module) script: `function app()` below becomes a global that the
 * shell references via x-data="app()". Loaded with `defer` BEFORE alpine.min.js so
 * the global exists before Alpine evaluates the DOM.
 *
 * Security: every value from the API is rendered with Alpine `x-text` (textContent)
 * in index.html — never x-html — so agent-authored strings can't inject markup.
 *
 * Control actions (spawn/kill/resume/approve/…) are async: the API enqueues a command
 * and the control worker executes it. enqueueAndTrack() posts the command, then polls
 * GET /commands/{id} until it reaches done/failed, surfacing the result in a banner.
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
    approvals: [],
    hosts: [],
    commands: [],

    // --- forms ---
    answerText: "",
    answerBusy: false,
    answerMsg: "",
    answerError: false,
    spawnForm: { name: "", role: "", placement: "worktree", worktree: "", subdir: "", task: "" },
    approvalForm: { branch: "", status: "approved", agent_name: "", sha: "", note: "" },
    projectForm: { id: "", root_dir: "", git_remote: "", credential_ref: "", _editing: false },
    hostForm: { hostname: "", forge_type: "github", token_env_var: "", base_url: "", _editing: false },
    sharedForm: { key: "", value: "" },

    // --- ui ---
    tab: "agents",
    lastError: "",
    cmd: { text: "", error: false, busy: false },
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
          const body = await res.json();
          detail = body.detail || detail;
          // Pydantic 422 returns a list of validation errors.
          if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
        } catch (_) {}
        const err = new Error(detail);
        err.status = res.status;
        throw err;
      }
      if (res.status === 204) return null;
      return res.json();
    },

    _sleep(ms) {
      return new Promise((r) => setTimeout(r, ms));
    },

    /* Post a control action, then poll its command to a terminal state. */
    async enqueueAndTrack(path, body, label) {
      this.cmd = { text: `${label}: queued…`, error: false, busy: true };
      try {
        const command = await this.api(path, { method: "POST", body });
        return await this._trackCommand(command.id, label);
      } catch (e) {
        if (e instanceof AuthError) return null;
        this.cmd = { text: `${label} failed: ${e.message}`, error: true, busy: false };
        return null;
      }
    },

    async _trackCommand(id, label) {
      for (let i = 0; i < 40; i++) {
        let c;
        try {
          c = await this.api(`/commands/${id}`);
        } catch (e) {
          if (e instanceof AuthError) return null;
          this.cmd = { text: `${label}: ${e.message}`, error: true, busy: false };
          return null;
        }
        if (c.status === "done" || c.status === "failed") {
          const ok = c.status === "done";
          const detail = c.error || (c.result ? JSON.stringify(c.result) : "");
          this.cmd = {
            text: `${label} ${ok ? "done" : "failed"}${detail ? " — " + detail : ""}`,
            error: !ok,
            busy: false,
          };
          return c;
        }
        this.cmd = { text: `${label}: ${c.status}…`, error: false, busy: true };
        await this._sleep(600);
      }
      this.cmd = { text: `${label}: still running (see Activity). Is the worker up?`, error: false, busy: false };
      return null;
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
        if (this.tab === "shared") return await this.loadShared();
        if (this.tab === "activity") return await this.loadCommands();
        if (this.tab === "hosts") return await this.loadHosts();
        if (this.tab === "projects") return await this.loadProjects();
        if (this.tab === "approvals") {
          if (this.selectedProjectId) await this.loadApprovals();
          return;
        }
        // agents tab
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

    switchTab(tab) {
      this.tab = tab;
      this.cmd = { text: "", error: false, busy: false };
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
      if (this.tab === "approvals") await this.loadApprovals();
    },

    resetProjectForm() {
      this.projectForm = { id: "", root_dir: "", git_remote: "", credential_ref: "", _editing: false };
    },
    editProject(p) {
      this.projectForm = {
        id: p.id,
        root_dir: p.root_dir,
        git_remote: p.git_remote || "",
        credential_ref: p.credential_ref || "",
        _editing: true,
      };
    },
    async saveProject() {
      const f = this.projectForm;
      const body = {
        root_dir: f.root_dir.trim(),
        git_remote: f.git_remote.trim() || null,
        credential_ref: f.credential_ref.trim() || null,
      };
      try {
        if (f._editing) {
          await this.api(`/projects/${encodeURIComponent(f.id)}`, { method: "PATCH", body });
          this.cmd = { text: `project '${f.id}' updated`, error: false, busy: false };
        } else {
          await this.api("/projects", { method: "POST", body: { id: f.id.trim(), ...body } });
          this.cmd = { text: `project '${f.id}' created`, error: false, busy: false };
        }
        this.resetProjectForm();
        await this.loadProjects();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
      }
    },
    async deleteProject(id) {
      if (!confirm(`Delete project '${id}'? Its agents/log rows go with it.`)) return;
      try {
        await this.api(`/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
        this.cmd = { text: `project '${id}' deleted`, error: false, busy: false };
        if (this.selectedProjectId === id) this.selectedProjectId = "";
        await this.loadProjects();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
      }
    },

    // --- agents ---
    async loadAgents() {
      const p = this.selectedProjectId;
      if (!p) return;
      this.agents = await this.api(`/projects/${encodeURIComponent(p)}/agents`);
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

    async spawnAgent() {
      const f = this.spawnForm;
      const body = { name: f.name.trim(), role: f.role || null, task: f.task.trim() || null };
      if (f.placement === "worktree" && f.worktree.trim()) body.worktree = f.worktree.trim();
      if (f.placement === "subdir" && f.subdir.trim()) body.subdir = f.subdir.trim();
      const p = encodeURIComponent(this.selectedProjectId);
      const final = await this.enqueueAndTrack(`/projects/${p}/agents/spawn`, body, `spawn ${body.name}`);
      if (final && final.status === "done") {
        this.spawnForm = { name: "", role: "", placement: "worktree", worktree: "", subdir: "", task: "" };
      }
      await this.loadAgents();
    },

    async killAgent(name) {
      const p = encodeURIComponent(this.selectedProjectId);
      await this.enqueueAndTrack(`/projects/${p}/agents/${encodeURIComponent(name)}/kill`, undefined, `kill ${name}`);
      await this.loadAgents();
    },

    async deleteAgent(name) {
      if (!confirm(`Delete the agent row '${name}'? (Kill the session first if live.)`)) return;
      const p = encodeURIComponent(this.selectedProjectId);
      try {
        await this.api(`/projects/${p}/agents/${encodeURIComponent(name)}`, { method: "DELETE" });
        this.cmd = { text: `agent row '${name}' deleted`, error: false, busy: false };
        if (this.selectedAgentName === name) this.selectedAgentName = null;
        await this.loadAgents();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
      }
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
          this.answerMsg = "Answer saved; resume enqueued.";
          this.answerText = "";
          await this.enqueueAndTrack(`${this._agentPath()}/resume`, { answer: text }, "resume");
          await this.loadAgents();
          await this.loadCheckmark();
          await this.loadLog();
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

    // --- approvals ---
    async loadApprovals() {
      if (!this.selectedProjectId) {
        this.approvals = [];
        return;
      }
      try {
        this.approvals = await this.api(`/projects/${encodeURIComponent(this.selectedProjectId)}/approvals`);
        this.lastError = "";
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },
    async submitApproval() {
      const f = this.approvalForm;
      const body = {
        branch: f.branch.trim(),
        status: f.status,
        agent_name: f.agent_name.trim() || null,
        sha: f.sha.trim() || null,
        note: f.note.trim() || null,
      };
      const p = encodeURIComponent(this.selectedProjectId);
      await this.enqueueAndTrack(`/projects/${p}/approvals`, body, `${f.status} ${f.branch}`);
      this.approvalForm = { branch: "", status: "approved", agent_name: "", sha: "", note: "" };
      await this.loadApprovals();
    },

    // --- hosts ---
    async loadHosts() {
      try {
        this.hosts = await this.api("/hosts");
        this.lastError = "";
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },
    resetHostForm() {
      this.hostForm = { hostname: "", forge_type: "github", token_env_var: "", base_url: "", _editing: false };
    },
    editHost(h) {
      this.hostForm = {
        hostname: h.hostname,
        forge_type: h.forge_type,
        token_env_var: h.token_env_var || "",
        base_url: h.base_url || "",
        _editing: true,
      };
    },
    async saveHost() {
      const f = this.hostForm;
      const body = {
        forge_type: f.forge_type,
        token_env_var: f.token_env_var.trim() || null,
        base_url: f.base_url.trim() || null,
      };
      try {
        if (f._editing) {
          await this.api(`/hosts/${encodeURIComponent(f.hostname)}`, { method: "PATCH", body });
          this.cmd = { text: `host '${f.hostname}' updated`, error: false, busy: false };
        } else {
          await this.api("/hosts", { method: "POST", body: { hostname: f.hostname.trim(), ...body } });
          this.cmd = { text: `host '${f.hostname}' created`, error: false, busy: false };
        }
        this.resetHostForm();
        await this.loadHosts();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
      }
    },
    async deleteHost(hostname) {
      if (!confirm(`Delete host '${hostname}'?`)) return;
      try {
        await this.api(`/hosts/${encodeURIComponent(hostname)}`, { method: "DELETE" });
        this.cmd = { text: `host '${hostname}' deleted`, error: false, busy: false };
        await this.loadHosts();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
      }
    },

    // --- activity / commands ---
    async loadCommands() {
      try {
        this.commands = await this.api("/commands?limit=50");
        this.lastError = "";
      } catch (e) {
        if (!(e instanceof AuthError)) this.lastError = e.message;
      }
    },
    async pollCiGlobal() {
      await this.enqueueAndTrack("/poll-ci", undefined, "poll-ci (all projects)");
      await this.loadCommands();
    },

    // --- shared tab ---
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
    async setSharedContext() {
      const key = this.sharedForm.key.trim();
      const value = this.sharedForm.value.trim();
      if (!key || !value) return;
      try {
        await this.api(`/shared/context/${encodeURIComponent(key)}`, { method: "PUT", body: { value } });
        this.cmd = { text: `shared context '${key}' set`, error: false, busy: false };
        this.sharedForm = { key: "", value: "" };
        await this.loadShared();
      } catch (e) {
        if (e instanceof AuthError) return;
        this.cmd = { text: e.message, error: true, busy: false };
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
