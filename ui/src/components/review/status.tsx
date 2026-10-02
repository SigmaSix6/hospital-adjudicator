import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleHelp,
  Info,
  MinusCircle,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CaseStatus, CheckOutcome, Severity } from "@/lib/types";

const pill = "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const map = {
    high: { label: "High", icon: AlertOctagon, cls: "border-error/30 bg-error-subtle text-error" },
    medium: { label: "Medium", icon: AlertTriangle, cls: "border-warning/30 bg-warning-subtle text-warning" },
    low: { label: "Low", icon: Info, cls: "border-info/30 bg-info-subtle text-info" },
  }[severity];
  const Icon = map.icon;
  return (
    <span className={cn(pill, map.cls, className)}>
      <Icon className="size-3.5" aria-hidden />
      {map.label} severity
    </span>
  );
}

export function StatusPill({ status, className }: { status: CaseStatus | null; className?: string }) {
  if (status === null)
    return (
      <span className={cn(pill, "border-border bg-muted text-muted-foreground", className)}>
        <CircleDashed className="size-3.5" aria-hidden />
        Not reviewed
      </span>
    );
  if (status === "needs_review")
    return (
      <span className={cn(pill, "border-warning/30 bg-warning-subtle text-warning", className)}>
        <ShieldAlert className="size-3.5" aria-hidden />
        Needs review
      </span>
    );
  return (
    <span className={cn(pill, "border-success/30 bg-success-subtle text-success", className)}>
      <ShieldCheck className="size-3.5" aria-hidden />
      No issues found
    </span>
  );
}

export function OutcomeBadge({ outcome }: { outcome: CheckOutcome }) {
  const map = {
    pass: { label: "Pass", icon: CheckCircle2, cls: "border-success/30 bg-success-subtle text-success" },
    issue: { label: "Issue", icon: XCircle, cls: "border-error/30 bg-error-subtle text-error" },
    undetermined: { label: "Undetermined", icon: CircleHelp, cls: "border-warning/30 bg-warning-subtle text-warning" },
    not_applicable: { label: "Not applicable", icon: MinusCircle, cls: "border-border bg-muted text-muted-foreground" },
  }[outcome];
  const Icon = map.icon;
  return (
    <span className={cn(pill, map.cls)}>
      <Icon className="size-3.5" aria-hidden />
      {map.label}
    </span>
  );
}

export function RuleTag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-brand-blue/20 bg-brand-blue-subtle px-1.5 py-0.5 font-mono text-[11px] font-medium text-brand-navy">
      {children}
    </span>
  );
}
