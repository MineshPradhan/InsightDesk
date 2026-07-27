export type Priority = "critical" | "high" | "medium" | "low";
export type Status = "new" | "triaged" | "in_progress" | "waiting_on_customer" | "resolved";

export interface TriageResult {
  id: number;
  predicted_queue: string;
  predicted_priority: Priority;
  queue_confidence: number;
  priority_confidence: number;
  sentiment: number;
  model_version: string;
  latency_ms: number;
  accepted_by_agent: boolean | null;
  queue_is_correct: boolean | null;
  created_at: string;
}

export interface Citation {
  n: number;
  chunk_id: string;
  article_id: number;
  title: string;
  similarity: number;
  rerank_score: number;
}

export interface ReplyDraft {
  id: number;
  text: string;
  citations: Citation[];
  grounded: boolean;
  model: string;
  latency_ms: number;
  agent_rating: number | null;
  was_sent: boolean;
  created_at: string;
}

export interface Ticket {
  id: string;
  external_id: string;
  subject: string;
  body?: string;
  queue: string;
  priority: Priority | "";
  status: Status;
  language: string;
  channel: string;
  received_at: string;
  csat: number | null;
  tags?: string[];
  latest_triage: TriageResult | null;
  triage_results?: TriageResult[];
  drafts?: ReplyDraft[];
}

export interface Overview {
  tickets: number;
  open: number;
  backlog_critical: number;
  median_resolution_minutes: number;
  p90_resolution_minutes: number;
  avg_csat: number;
  triage_accuracy: number;
  triage_p50_latency_ms: number;
  drafts_generated: number;
  drafts_grounded_pct: number;
  drafts_sent_pct: number;
}
