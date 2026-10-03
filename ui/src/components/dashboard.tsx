"use client";

import {
  AlertCircle,
  ClipboardCheck,
  FileWarning,
  Loader2,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type {
  CaseDetail,
  CaseListItem,
  Finding,
  Health,
  LlmCallsResponse,
  LlmMode,
  ReviewResult,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChecksView, LlmAuditView, RawJsonView } from "./review/details";
import { DocumentsView, evidenceKey } from "./review/documents";
import { FindingCard } from "./review/findings";
import { StatusPill } from "./review/status";

type Health_ =
  | { state: "loading" }
  | { state: "ok"; data: Health }
  | { state: "error"; message: string };

function Header({ health }: { health: Health_ }) {
  return (
    <header className="border-b-4 border-brand-yellow bg-brand-navy text-white">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-4 py-4 sm:px-6">
        <div className="flex size-10 items-center justify-center rounded-xl bg-brand-blue">
          <Stethoscope className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">
            Clinical Document Review
          </h1>
          <p className="text-sm text-white/75">
            Pre-claim review assistant · findings with SOP references and source
            evidence · synthetic data
          </p>
        </div>
        <div aria-live="polite">
          {health.state === "loading" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs">
              <Loader2 className="size-3.5 animate-spin" aria-hidden />{" "}
              Connecting to API
            </span>
          )}
          {health.state === "error" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-error px-3 py-1 text-xs font-medium">
              <WifiOff className="size-3.5" aria-hidden /> API offline
            </span>
          )}
          {health.state === "ok" && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs">
              <span
                className={cn(
                  "size-2 rounded-full",
                  health.data.gemini_configured
                    ? "bg-brand-yellow"
                    : "bg-white/60",
                )}
                aria-hidden
              />
              {health.data.gemini_configured
                ? `Gemini ready · ${health.data.gemini_model}`
                : "Mock LLM only (no API key)"}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}

function Stat({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  icon: typeof ShieldAlert;
  tone: string;
}) {
  return (
    <Card className="gap-0 py-4">
      <CardContent className="flex items-center gap-3 px-4">
        <div
          className={cn(
            "flex size-9 items-center justify-center rounded-lg",
            tone,
          )}
        >
          <Icon className="size-4.5" aria-hidden />
        </div>
        <div>
          <div className="text-xl font-semibold tabular-nums">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function ModeToggle({
  mode,
  setMode,
  liveAvailable,
}: {
  mode: LlmMode;
  setMode: (m: LlmMode) => void;
  liveAvailable: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="LLM mode"
      className="grid grid-cols-2 rounded-lg border bg-muted p-0.5"
    >
      {(["live", "mock"] as const).map((m) => {
        const disabled = m === "live" && !liveAvailable;
        return (
          <button
            key={m}
            role="radio"
            aria-checked={mode === m}
            disabled={disabled}
            onClick={() => setMode(m)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
              mode === m
                ? "bg-card text-brand-navy shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {m === "live" ? "Live Gemini" : "Mock LLM"}
          </button>
        );
      })}
    </div>
  );
}

function CaseList({
  cases,
  selected,
  onSelect,
  busyCase,
}: {
  cases: CaseListItem[] | null;
  selected: string | null;
  onSelect: (id: string) => void;
  busyCase: string | null;
}) {
  if (cases === null)
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  return (
    <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-1">
      {cases.map((c) => (
        <li key={c.case_id}>
          <button
            onClick={() => onSelect(c.case_id)}
            aria-current={selected === c.case_id}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              selected === c.case_id
                ? "border-brand-blue bg-brand-blue-subtle"
                : "border-transparent hover:border-border hover:bg-muted/60",
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 font-mono text-sm font-semibold">
                {c.case_id}
                {busyCase === c.case_id && (
                  <Loader2
                    className="size-3.5 animate-spin text-brand-blue"
                    aria-label="Reviewing"
                  />
                )}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {c.document_count} documents
                {c.missing_core_documents.length > 0 && (
                  <> · missing {c.missing_core_documents.join(", ")}</>
                )}
              </div>
            </div>
            <StatusPill status={c.latest_status} />
          </button>
        </li>
      ))}
    </ul>
  );
}

function ReviewPanel({
  caseId,
  detail,
  result,
  loading,
  reviewing,
  error,
  onRun,
}: {
  caseId: string | null;
  detail: CaseDetail | null;
  result: ReviewResult | null;
  loading: boolean;
  reviewing: boolean;
  error: string | null;
  onRun: () => void;
}) {
  const [tab, setTab] = useState("findings");
  const [focus, setFocus] = useState<Finding | null>(null);

  const highlighted = useMemo(() => {
    const src = focus ? [focus] : (result?.findings ?? []);
    return new Set(
      src.flatMap((f) => f.evidence.map((e) => evidenceKey(e.file, e.field))),
    );
  }, [focus, result]);

  if (!caseId)
    return (
      <Card className="items-center justify-center py-16 text-center">
        <ClipboardCheck className="size-10 text-brand-blue" aria-hidden />
        <CardTitle>Select a case to begin</CardTitle>
        <p className="max-w-md text-sm text-muted-foreground">
          Pick a patient case on the left, then run a review. Each review parses
          the case documents, applies the SOP rules, and returns findings with
          the exact document fields used as evidence.
        </p>
      </Card>
    );

  const runButton = (
    <Button onClick={onRun} disabled={reviewing} size="lg">
      {reviewing ? (
        <Loader2 className="animate-spin" aria-hidden />
      ) : result ? (
        <RefreshCw aria-hidden />
      ) : (
        <PlayCircle aria-hidden />
      )}
      {reviewing ? "Reviewing…" : result ? "Re-run review" : "Run review"}
    </Button>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-mono text-2xl font-semibold tracking-tight">
            {caseId}
          </h2>
          <p className="text-sm text-muted-foreground">
            {detail
              ? detail.documents.map((d) => d.document_type).join(" · ")
              : "Loading documents…"}
          </p>
        </div>
        {runButton}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertTitle>Review failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {reviewing && (
        <Card className="gap-3 py-4" aria-busy>
          <CardContent className="space-y-3 px-4">
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2
                className="size-4 animate-spin text-brand-blue"
                aria-hidden
              />
              Parsing documents, applying SOP-01/02/04/05 rules, and running the
              SOP-03 diagnosis comparison…
            </p>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-40 w-full" />
          </CardContent>
        </Card>
      )}

      {!reviewing && loading && <Skeleton className="h-48 w-full" />}

      {!reviewing && !loading && !result && !error && (
        <Card className="items-center py-12 text-center">
          <Sparkles className="size-8 text-brand-blue" aria-hidden />
          <CardTitle>This case has not been reviewed yet</CardTitle>
          <p className="max-w-md text-sm text-muted-foreground">
            Run a review to see the case status, findings, rule checks, and the
            evidence behind each finding.
          </p>
          {runButton}
        </Card>
      )}

      {!reviewing && result && (
        <>
          <Card
            className={cn(
              "gap-2 border-l-4 py-4",
              result.status === "needs_review"
                ? "border-l-warning bg-warning-subtle/40"
                : "border-l-success bg-success-subtle/40",
            )}
          >
            <CardContent className="space-y-2 px-4">
              <div className="flex flex-wrap items-center gap-2">
                {result.status === "needs_review" ? (
                  <ShieldAlert className="size-5 text-warning" aria-hidden />
                ) : (
                  <ShieldCheck className="size-5 text-success" aria-hidden />
                )}
                <span className="text-lg font-semibold">
                  {result.status === "needs_review"
                    ? "Needs human review"
                    : "No issues found"}
                </span>
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {result.status}
                </code>
                <span className="ml-auto text-xs text-muted-foreground">
                  run {result.run_id} ·{" "}
                  {result.audit.llm_mode === "live"
                    ? `Gemini ${result.audit.llm_model}`
                    : "mock LLM"}{" "}
                  · {new Date(result.audit.timestamp).toLocaleString()}
                </span>
              </div>
              <p className="text-sm">{result.summary}</p>
              {result.human_review_reasons.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-5 text-sm">
                  {result.human_review_reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              )}
              {result.uncertainties.length > 0 && (
                <div className="rounded-lg bg-brand-yellow-subtle px-3 py-2 text-sm text-brand-navy">
                  <span className="font-medium">Uncertainties: </span>
                  {result.uncertainties.join(" ")}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                {result.decision_boundary}
              </p>
            </CardContent>
          </Card>

          <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
            <div className="overflow-x-auto">
              <TabsList>
                <TabsTrigger value="findings">
                  Findings ({result.findings.length})
                </TabsTrigger>
                <TabsTrigger value="checks">
                  Rule checks ({result.checks.length})
                </TabsTrigger>
                <TabsTrigger value="documents">
                  Documents ({detail?.documents.length ?? 0})
                </TabsTrigger>
                <TabsTrigger value="llm">LLM &amp; audit</TabsTrigger>
                <TabsTrigger value="json">Raw JSON</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="findings" className="mt-3 space-y-3">
              {result.findings.length === 0 ? (
                <Card className="items-center py-10 text-center">
                  <ShieldCheck className="size-8 text-success" aria-hidden />
                  <CardTitle>No findings</CardTitle>
                  <p className="max-w-md text-sm text-muted-foreground">
                    All configured rule checks passed. See the Rule checks tab
                    for what was verified.
                  </p>
                </Card>
              ) : (
                result.findings.map((f) => (
                  <FindingCard
                    key={f.finding_id}
                    finding={f}
                    onShowEvidence={(fd) => {
                      setFocus(fd);
                      setTab("documents");
                    }}
                  />
                ))
              )}
            </TabsContent>
            <TabsContent value="checks" className="mt-3">
              <ChecksView checks={result.checks} />
            </TabsContent>
            <TabsContent value="documents" className="mt-3 space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span
                  className="inline-block size-3 rounded-sm border bg-brand-yellow-subtle"
                  aria-hidden
                />
                {focus ? (
                  <>
                    Highlighting evidence for{" "}
                    <span className="font-medium text-foreground">
                      {focus.title}
                    </span>
                    <Button
                      variant="link"
                      size="sm"
                      className="h-auto p-0"
                      onClick={() => setFocus(null)}
                    >
                      Show evidence for all findings
                    </Button>
                  </>
                ) : (
                  "Highlighted rows are cited as evidence by at least one finding."
                )}
              </div>
              {detail && (
                <DocumentsView
                  documents={detail.documents}
                  highlighted={highlighted}
                />
              )}
            </TabsContent>
            <TabsContent value="llm" className="mt-3">
              <LlmAuditView result={result} />
            </TabsContent>
            <TabsContent value="json" className="mt-3">
              <RawJsonView result={result} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

export function Dashboard() {
  const [health, setHealth] = useState<Health_>({ state: "loading" });
  const [cases, setCases] = useState<CaseListItem[] | null>(null);
  const [usage, setUsage] = useState<LlmCallsResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [loadingCase, setLoadingCase] = useState(false);
  const [busyCase, setBusyCase] = useState<string | null>(null);
  const [batch, setBatch] = useState<{ done: number; total: number } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<LlmMode>("mock");
  const [useCache, setUseCache] = useState(true);

  const refreshList = useCallback(async () => {
    try {
      const [c, u] = await Promise.all([api.cases(), api.llmCalls()]);
      setCases(c);
      setUsage(u);
    } catch (e) {
      setHealth({ state: "error", message: (e as Error).message });
    }
  }, []);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth({ state: "ok", data: h });
        setMode(h.default_llm_mode);
        return refreshList();
      })
      .catch((e) =>
        setHealth({ state: "error", message: (e as Error).message }),
      );
  }, [refreshList]);

  const selectCase = (id: string) => {
    if (id === selected) return;
    setLoadingCase(true);
    setError(null);
    setDetail(null);
    setResult(null);
    setSelected(id);
  };

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    Promise.all([api.caseDetail(selected), api.latestReview(selected)])
      .then(([d, r]) => {
        if (cancelled) return;
        setDetail(d);
        setResult(r);
      })
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoadingCase(false));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const runOne = async (id: string) => {
    setBusyCase(id);
    setError(null);
    try {
      const r = await api.review(id, mode, useCache);
      if (id === selected) setResult(r);
      return r;
    } catch (e) {
      if (id === selected) setError((e as Error).message);
      return null;
    } finally {
      setBusyCase(null);
    }
  };

  const runAll = async () => {
    if (!cases) return;
    setBatch({ done: 0, total: cases.length });
    for (let i = 0; i < cases.length; i++) {
      await runOne(cases[i].case_id);
      setBatch({ done: i + 1, total: cases.length });
      await refreshList();
    }
    setBatch(null);
  };

  const reviewed = cases?.filter((c) => c.latest_status) ?? [];
  const needsReview = reviewed.filter(
    (c) => c.latest_status === "needs_review",
  ).length;
  const liveAvailable = health.state === "ok" && health.data.gemini_configured;
  const busy = busyCase !== null || batch !== null;

  return (
    <div className="flex min-h-full flex-col">
      <Header health={health} />
      <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-5 px-4 py-5 sm:px-6">
        {health.state === "error" && (
          <Alert variant="destructive">
            <WifiOff aria-hidden />
            <AlertTitle>Cannot reach the review API</AlertTitle>
            <AlertDescription>
              {health.message} Start the API (see README) and reload this page.
            </AlertDescription>
          </Alert>
        )}

        <section
          aria-label="Overview"
          className="grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          <Stat
            label="Cases in manifest"
            value={cases ? String(cases.length) : "–"}
            icon={ClipboardCheck}
            tone="bg-brand-blue-subtle text-brand-blue"
          />
          <Stat
            label="Need human review"
            value={cases ? String(needsReview) : "–"}
            icon={ShieldAlert}
            tone="bg-warning-subtle text-warning"
          />
          <Stat
            label="No issues found"
            value={cases ? String(reviewed.length - needsReview) : "–"}
            icon={ShieldCheck}
            tone="bg-success-subtle text-success"
          />
          <Stat
            label={
              usage ? `LLM spend · ${usage.total_calls} calls` : "LLM spend"
            }
            value={usage ? `$${usage.total_cost_usd.toFixed(4)}` : "–"}
            icon={FileWarning}
            tone="bg-brand-yellow-subtle text-brand-navy"
          />
        </section>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[340px_1fr]">
          <aside className="min-w-0 space-y-3 lg:sticky lg:top-5 lg:self-start">
            <Card className="gap-3 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Run settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 px-4">
                <ModeToggle
                  mode={mode}
                  setMode={setMode}
                  liveAvailable={liveAvailable}
                />
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="cache" className="text-sm font-normal">
                    Reuse cached LLM answers
                  </Label>
                  <Switch
                    id="cache"
                    checked={useCache}
                    onCheckedChange={(v) => setUseCache(Boolean(v))}
                  />
                </div>
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={runAll}
                  disabled={busy || !cases || health.state !== "ok"}
                >
                  {batch ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <PlayCircle aria-hidden />
                  )}
                  {batch
                    ? `Reviewing ${batch.done + 1 > batch.total ? batch.total : batch.done + 1} of ${batch.total}…`
                    : "Review all cases"}
                </Button>
              </CardContent>
            </Card>
            <Card className="gap-3 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Patient cases</CardTitle>
              </CardHeader>
              <CardContent className="px-2">
                <CaseList
                  cases={cases}
                  selected={selected}
                  onSelect={selectCase}
                  busyCase={busyCase}
                />
              </CardContent>
            </Card>
          </aside>

          <section aria-label="Case review" className="min-w-0">
            <ReviewPanel
              key={`${selected}-${result?.run_id ?? "none"}`}
              caseId={selected}
              detail={detail}
              result={result}
              loading={loadingCase}
              reviewing={busyCase === selected && selected !== null}
              error={error}
              onRun={async () => {
                if (!selected) return;
                await runOne(selected);
                await refreshList();
              }}
            />
          </section>
        </div>
      </main>
      <footer className="border-t bg-card">
        <div className="mx-auto max-w-[1400px] px-4 py-3 text-xs text-muted-foreground sm:px-6">
          Decision support only: the assistant never approves, rejects, or
          denies a claim.
        </div>
      </footer>
    </div>
  );
}
