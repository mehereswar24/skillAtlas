/**
 * Portfolio DTOs, mirroring `backend/app/schemas/portfolio.py`.
 *
 * Kept here rather than in `src/lib/types.ts` so the public page and the
 * owner's settings can share them without either of them owning the file.
 *
 * The split matters: `PublicPortfolio` is what an anonymous visitor receives,
 * and it has no field that can carry an email address or a user id. If you
 * find yourself wanting to add one, add it to `PortfolioSettings` instead.
 */

export type PublicLinks = {
  github: string | null;
  linkedin: string | null;
  website: string | null;
};

export type PublicProjectFile = {
  path: string;
  content: string;
  is_readonly: boolean;
  is_entry: boolean;
};

export type PublicTest = {
  id: number;
  name: string;
  kind: 'python-assert' | 'dom-assert' | 'sql-result';
  code: string;
  expected: string | null;
  is_hidden: boolean;
};

export type PublicProject = {
  slug: string;
  title: string;
  tagline: string;
  note: string;
  runtime: 'python' | 'web' | 'sql';
  difficulty: string;
  concept_slug: string;
  concept_name: string;
  xp_reward: number;
  shipped_at: string;
  tests_passed: number;
  tests_total: number;
  attempts: number;
  /** Empty unless the learner opted into publishing their code. */
  files: PublicProjectFile[];
  tests: PublicTest[];
  entry_path: string | null;
};

export type PublicConcept = {
  slug: string;
  name: string;
  difficulty: string;
  est_hours: number;
};

export type PublicTrackGroup = {
  slug: string;
  title: string;
  completed: PublicConcept[];
  track_total: number;
};

export type PublicBadge = {
  slug: string;
  name: string;
  description: string | null;
  icon: string;
  awarded_at: string;
};

export type PublicReadiness = {
  slug: string;
  title: string;
  percent: number;
};

export type PublicPortfolio = {
  handle: string;
  display_name: string;
  headline: string;
  bio: string;
  location: string;
  links: PublicLinks;
  joined_at: string;
  projects: PublicProject[];
  tracks: PublicTrackGroup[];
  badges: PublicBadge[];
  readiness: PublicReadiness[];
  points: number | null;
  level: number | null;
  concepts_completed: number | null;
  projects_shipped: number | null;
  /** The owner previewing an unpublished page. Visitors never see this true. */
  is_preview: boolean;
};

export type PortfolioVisibility = {
  show_projects: boolean;
  show_concepts: boolean;
  show_points: boolean;
  show_badges: boolean;
  show_readiness: boolean;
  show_project_code: boolean;
};

export type OwnerProject = {
  project_id: number;
  slug: string;
  title: string;
  tagline: string;
  runtime: string;
  concept_name: string;
  shipped_at: string;
  is_visible: boolean;
  note: string;
  sort_order: number;
};

export type PortfolioSettings = {
  exists: boolean;
  handle: string | null;
  display_name: string;
  headline: string;
  bio: string;
  location: string;
  github_url: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  visibility: PortfolioVisibility;
  is_published: boolean;
  published_at: string | null;
  public_url: string | null;
  projects: OwnerProject[];
  /** What a stranger can see right now, in words. */
  public_summary: string[];
};

export type HandleCheck = {
  handle: string;
  available: boolean;
  reason: string | null;
};
