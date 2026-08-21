/** Wire types for the mock interview API (`/api/v1/interviews`). */

export type Verdict = 'strong' | 'adequate' | 'weak' | 'no-answer' | 'ungraded';

export type RoundOption = {
  name: string;
  label: string;
  question_count: number;
};

export type InterviewRoleOption = {
  company_slug: string;
  company_name: string;
  company_icon: string;
  role_slug: string;
  role_title: string;
  level: string;
  question_count: number;
  rounds: RoundOption[];
  attempts: number;
  best_score: number | null;
};

export type InterviewTurn = {
  id: number;
  position: number;
  round: string;
  round_label: string;
  topic: string | null;
  difficulty: string;
  question: string;
  source_name: string | null;
  source_url: string | null;
  answer_text: string | null;
  verdict: Verdict | null;
  score: number | null;
  feedback_md: string | null;
  missed_points: string[];
  injection_flagged: boolean;
  answered_at: string | null;
  reference_answer_md: string | null;
};

export type ConceptSuggestion = {
  slug: string;
  name: string;
  summary: string;
  reason: string;
  is_completed: boolean;
  in_roadmap: boolean;
};

export type SessionSummary = {
  score: number | null;
  graded_count: number;
  answered_count: number;
  question_count: number;
  strengths: string[];
  weak_areas: string[];
  recommended_concepts: ConceptSuggestion[];
  summary_md: string;
  degraded: boolean;
};

export type SessionRow = {
  id: number;
  company_slug: string;
  company_name: string;
  role_slug: string;
  role_title: string;
  status: 'in-progress' | 'completed';
  score: number | null;
  question_count: number;
  answered_count: number;
  was_degraded: boolean;
  created_at: string;
  completed_at: string | null;
};

export type InterviewSession = SessionRow & {
  turns: InterviewTurn[];
  summary: SessionSummary | null;
  grading_available: boolean;
};

export type InterviewStatus = {
  available: boolean;
  model: string | null;
  mode: 'graded' | 'ungraded';
};

export const VERDICT_STYLE: Record<Verdict, { label: string; className: string }> = {
  strong: {
    label: 'Strong answer',
    className: 'border-success/50 bg-success/10 text-success',
  },
  adequate: {
    label: 'Partly there',
    className: 'border-primary/50 bg-primary/10 text-primary',
  },
  weak: {
    label: 'Weak answer',
    className: 'border-destructive/50 bg-destructive/10 text-destructive',
  },
  'no-answer': {
    label: 'Passed on it',
    className: 'border-border bg-muted text-muted-foreground',
  },
  ungraded: {
    label: 'Not graded',
    className: 'border-border bg-muted text-muted-foreground',
  },
};
