/* Design-system primitives ported from the Leeworks kit: flat, dark, border-led.
 * Every value rendered here comes from the API and is placed via React children /
 * textContent — never dangerouslySetInnerHTML — so agent-authored strings stay inert. */
"use client";

import type { ReactNode, ChangeEvent } from "react";
import type { Tone } from "@/lib/format";
import { statusLabel, statusTone } from "@/lib/format";

export function Badge({
  tone = "neutral",
  pill = false,
  dot = false,
  children,
}: {
  tone?: Tone;
  pill?: boolean;
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`badge badge-${tone}${pill ? " pill" : ""}`}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}

/** Status badge that maps a raw handler status string to a tone + tidy label. */
export function StatusBadge({ status }: { status: string | null | undefined }) {
  return <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>;
}

export function Card({
  children,
  interactive = false,
  onClick,
  className = "",
}: {
  children: ReactNode;
  interactive?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div
      className={`card${interactive ? " interactive" : ""} ${className}`.trim()}
      onClick={onClick}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {children}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export function Button({
  variant = "secondary",
  size = "md",
  onClick,
  disabled,
  type = "button",
  children,
}: {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  children: ReactNode;
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant}${size === "sm" ? " btn-sm" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function Field({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <label className="field">
      {label && <span className="field-label">{label}</span>}
      {children}
    </label>
  );
}

export function Input({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  disabled,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <Field label={label}>
      <input
        className="input"
        type={type}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
    </Field>
  );
}

export function Textarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <Field label={label}>
      <textarea
        className="textarea"
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
    </Field>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <Field label={label}>
      <select
        className="select"
        value={value}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          className={`tab${value === t.value ? " active" : ""}`}
          onClick={() => onChange(t.value)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Stat({
  value,
  label,
  sub,
  accent = false,
}: {
  value: ReactNode;
  label: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div>
      <div className={`stat-value${accent ? " accent" : ""}`}>{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Callout({
  tone = "info",
  children,
}: {
  tone?: "info" | "danger" | "success";
  children: ReactNode;
}) {
  return <div className={`callout callout-${tone}`}>{children}</div>;
}

/** Renders a unified-diff / patch, tinting +/- lines. Content is textContent. */
export function CodeBlock({
  code,
  language,
  title,
}: {
  code: string;
  language?: string;
  title?: string;
}) {
  const lines = code.split("\n");
  return (
    <div className="codeblock">
      {(title || language) && (
        <div className="codeblock-head">
          <span>{title ?? ""}</span>
          <span>{language ?? ""}</span>
        </div>
      )}
      <pre>
        {lines.map((line, i) => {
          const cls = line.startsWith("+")
            ? "diff-add"
            : line.startsWith("-")
              ? "diff-del"
              : undefined;
          return (
            <span key={i} className={cls}>
              {line}
              {i < lines.length - 1 ? "\n" : ""}
            </span>
          );
        })}
      </pre>
    </div>
  );
}

export function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`toggle${on ? " on" : ""}`}
      aria-pressed={on}
      onClick={onClick}
    >
      <span className="knob" />
    </button>
  );
}
