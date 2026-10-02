"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CheckResult, ReviewResult } from "@/lib/types";
import { OutcomeBadge, RuleTag } from "./status";

export function ChecksView({ checks }: { checks: CheckResult[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Rule</th>
            <th className="px-3 py-2 font-medium">Check</th>
            <th className="px-3 py-2 font-medium">Outcome</th>
            <th className="px-3 py-2 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((c, i) => (
            <tr key={i} className="border-t align-top">
              <td className="px-3 py-2">
                <RuleTag>{c.rule_id}</RuleTag>
              </td>
              <td className="px-3 py-2">{c.description}</td>
              <td className="px-3 py-2">
                <OutcomeBadge outcome={c.outcome} />
              </td>
              <td className="min-w-64 px-3 py-2 text-muted-foreground">{c.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Kv({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-2 border-t py-1.5 text-sm first:border-t-0">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-[13px] break-all">{v}</dd>
    </div>
  );
}

export function LlmAuditView({ result }: { result: ReviewResult }) {
  const a = result.audit;
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="gap-3 py-4">
        <CardHeader className="px-4">
          <CardTitle className="text-base">LLM calls</CardTitle>
          <p className="text-sm text-muted-foreground">
            Only the SOP-03 diagnosis comparison uses the LLM. It is skipped when the claim diagnosis is blank or
            matches the discharge diagnosis exactly.
          </p>
        </CardHeader>
        <CardContent className="px-4">
          {result.llm_calls.length === 0 ? (
            <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              No LLM call was needed for this case. Every check was decided by deterministic rules.
            </p>
          ) : (
            result.llm_calls.map((c, i) => (
              <dl key={i} className="rounded-lg border px-3 py-1">
                <Kv k="Step" v={c.step} />
                <Kv k="Provider / model" v={`${c.provider} / ${c.model}`} />
                <Kv k="Tokens in / out" v={`${c.input_tokens} / ${c.output_tokens} (${c.token_source.replaceAll("_", " ")})`} />
                <Kv k="Estimated cost" v={`USD ${c.cost_usd.toFixed(6)}`} />
                <Kv k="Latency" v={`${c.latency_ms} ms`} />
                <Kv k="Retries" v={c.retries} />
                <Kv k="Cache" v={c.cache_status} />
                <Kv k="Status" v={c.status} />
              </dl>
            ))
          )}
        </CardContent>
      </Card>
      <Card className="gap-3 py-4">
        <CardHeader className="px-4">
          <CardTitle className="text-base">Audit record</CardTitle>
          <p className="text-sm text-muted-foreground">Stored with every run so the result can be traced later (SOP-07).</p>
        </CardHeader>
        <CardContent className="px-4">
          <dl className="rounded-lg border px-3 py-1">
            <Kv k="Run ID" v={a.run_id} />
            <Kv k="Timestamp" v={a.timestamp} />
            <Kv k="Run label" v={a.run_label} />
            <Kv k="Rule set" v={a.rule_set_version} />
            <Kv k="Prompt version" v={a.prompt_version} />
            <Kv k="LLM mode / model" v={`${a.llm_mode} / ${a.llm_model}`} />
            <Kv k="SOP versions" v={Object.entries(a.sop_versions).map(([k, v]) => `${k} ${v}`).join(", ")} />
            <Kv
              k="Input documents"
              v={a.input_documents.map((d) => `${d.file.split("/").pop()} (${d.sha256.slice(0, 10)})`).join(", ")}
            />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

export function RawJsonView({ result }: { result: ReviewResult }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(result, null, 2);
  return (
    <div className="relative rounded-xl border bg-brand-navy">
      <Button
        size="sm"
        variant="secondary"
        className="absolute top-3 right-3"
        onClick={async () => {
          await navigator.clipboard.writeText(json);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? "Copied" : "Copy JSON"}
      </Button>
      <pre className="max-h-[70vh] overflow-auto p-4 font-mono text-xs leading-relaxed text-white">{json}</pre>
    </div>
  );
}
