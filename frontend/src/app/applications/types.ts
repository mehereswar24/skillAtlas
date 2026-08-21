/** Shapes returned by `backend/app/schemas/application.py`.
 *
 * Kept beside the route rather than in `lib/types.ts` because nothing else in
 * the app reads an application.
 */

export type Stage =
  | 'saved'
  | 'applied'
  | 'screen'
  | 'onsite'
  | 'offer'
  | 'rejected'
  | 'withdrawn';

export type StageInfo = {
  value: Stage;
  label: string;
  is_terminal: boolean;
};

export type CompanyRef = { slug: string; name: string; icon: string };
export type CompanyRoleRef = { slug: string; title: string; level: string };

export type ApplicationSummary = {
  id: number;
  company_name: string;
  role_title: string;
  stage: Stage;
  location: string | null;
  salary_note: string | null;
  source_url: string | null;
  applied_on: string | null;
  has_job_description: boolean;
  has_notes: boolean;
  company: CompanyRef | null;
  company_role: CompanyRoleRef | null;
  created_at: string;
  updated_at: string;
  last_moved_at: string | null;
};

export type ApplicationEvent = {
  id: number;
  from_stage: Stage | null;
  to_stage: Stage;
  note: string | null;
  occurred_at: string;
};

export type MissingConcept = {
  slug: string;
  name: string;
  weight: number;
  adds_percent: number;
  is_in_roadmap: boolean;
};

export type PrepFocusArea = {
  label: string;
  notes: string | null;
  weight: number;
  concept_slug: string | null;
  concept_name: string | null;
  is_completed: boolean;
};

export type ApplicationPrep = {
  company: CompanyRef;
  company_role: CompanyRoleRef | null;
  hiring_process_md: string | null;
  fetched_on: string | null;
  focus_md: string | null;
  focus_areas: PrepFocusArea[];
  focus_readiness_percent: number;
  role_readiness_percent: number | null;
  role_slug: string | null;
  missing: MissingConcept[];
  question_count: number;
};

export type ApplicationDetail = ApplicationSummary & {
  job_description: string | null;
  notes: string | null;
  events: ApplicationEvent[];
  prep: ApplicationPrep | null;
};

export type BoardColumn = {
  stage: Stage;
  label: string;
  is_terminal: boolean;
  applications: ApplicationSummary[];
};

export type ApplicationBoard = {
  columns: BoardColumn[];
  total: number;
  active: number;
};

/** Colour per stage, so a card reads the same on the board and on its page. */
export const STAGE_TONE: Record<Stage, string> = {
  saved: 'text-muted-foreground',
  applied: 'text-primary',
  screen: 'text-primary',
  onsite: 'text-primary',
  offer: 'text-success',
  rejected: 'text-destructive',
  withdrawn: 'text-muted-foreground',
};
