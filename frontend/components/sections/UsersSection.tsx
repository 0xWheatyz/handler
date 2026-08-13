/* Users — admin-only account management. Invite by email (the invitee sets their own
 * password through a one-shot link, emailed when SMTP is configured and always shown
 * here), toggle admin, disable, delete, and mint reset links. Deleting a user turns
 * their projects/skills/tools into shared resources rather than removing them. */
"use client";

import { useState } from "react";
import { useDashboard } from "@/components/store";
import { Button } from "@/components/ui";
import { fmtFull } from "@/lib/format";

export function UsersSection() {
  const s = useDashboard();
  const [email, setEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [lastLink, setLastLink] = useState<{ email: string; url: string } | null>(null);

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    const created = await s.createUser(email, isAdmin);
    if (created) {
      setLastLink({ email: created.user.email, url: created.invite_url });
      setEmail("");
      setIsAdmin(false);
    }
  };

  const resetLink = async (id: number, userEmail: string) => {
    const link = await s.mintResetLink(id);
    if (link) setLastLink({ email: userEmail, url: link.reset_url });
  };

  const isSelf = (id: number) => s.me?.kind === "user" && s.me.user_id === id;

  return (
    <>
      <div className="section-head">
        <div className="section-title">Users</div>
        <div className="section-desc">
          Accounts for this Handler. Each user&apos;s projects, skills, and tools are
          theirs alone; shared (unowned) resources are visible to everyone and managed by
          admins.
        </div>
      </div>
      <div className="section-body vstack" style={{ gap: 16 }}>
        <form className="hstack" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={invite}>
          <input
            className="input"
            type="email"
            placeholder="new-user@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ maxWidth: 320 }}
            required
          />
          <label className="hstack muted" style={{ gap: 6, fontSize: "var(--text-sm)" }}>
            <input
              type="checkbox"
              checked={isAdmin}
              onChange={(e) => setIsAdmin(e.target.checked)}
            />
            admin
          </label>
          <Button type="submit" disabled={s.cmd.busy}>
            Invite user
          </Button>
        </form>

        {lastLink && (
          <div className="callout callout-info vstack" style={{ gap: 6 }}>
            <span>
              One-shot set-password link for <strong>{lastLink.email}</strong> (share it over
              a channel you trust; it expires):
            </span>
            <code
              className="mono"
              style={{ wordBreak: "break-all", userSelect: "all", fontSize: "var(--text-xs)" }}
            >
              {lastLink.url}
            </code>
          </div>
        )}

        {s.users.length === 0 ? (
          <div className="empty">No users loaded (admin access required).</div>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {s.users.map((u) => (
                  <tr key={u.id}>
                    <td className="mono">
                      {u.email}
                      {isSelf(u.id) ? <span className="faint"> (you)</span> : null}
                    </td>
                    <td>{u.is_admin ? "admin" : "user"}</td>
                    <td className={u.disabled ? "faint" : undefined}>
                      {u.disabled
                        ? "disabled"
                        : u.has_password
                          ? "active"
                          : "invited — awaiting password"}
                    </td>
                    <td className="faint nowrap">{fmtFull(u.created_at)}</td>
                    <td>
                      <div className="hstack" style={{ gap: 6, justifyContent: "flex-end" }}>
                        <Button
                          variant="secondary"
                          onClick={() => void s.updateUser(u.id, { is_admin: !u.is_admin })}
                        >
                          {u.is_admin ? "Demote" : "Make admin"}
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => void s.updateUser(u.id, { disabled: !u.disabled })}
                        >
                          {u.disabled ? "Enable" : "Disable"}
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => void resetLink(u.id, u.email)}
                        >
                          Reset link
                        </Button>
                        <Button
                          variant="danger"
                          disabled={isSelf(u.id)}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Remove ${u.email}? Their projects, skills, and tools become shared.`,
                              )
                            ) {
                              void s.deleteUser(u.id);
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
