/** Shapes returned by the SkillAtlas API. Mirrors `backend/app/schemas`. */

export type Domain = {
  id: number;
  slug: string;
  name: string;
  category: string;
  icon: string;
  color: string;
  description: string | null;
  has_content: boolean;
};

export type TrackSummary = {
  id: number;
  slug: string;
  title: string;
  target_role: string;
  description: string | null;
  difficulty: string;
  domain_slug: string;
  concept_count: number;
  total_hours: number;
};

export type ConceptSummary = {
  id: number;
  slug: string;
  name: string;
  summary: string;
  est_hours: number;
  difficulty: string;
  domain_slug: string;
};

export type TrackDetail = TrackSummary & { concepts: ConceptSummary[] };

export type Resource = {
  id: number;
  kind: 'video' | 'doc' | 'book' | 'course' | 'project' | 'article';
  title: string;
  url: string;
  provider: string | null;
  duration_min: number | null;
  is_free: boolean;
};

export type QuizOption = { id: number; text: string };
export type QuizQuestion = { id: number; prompt: string; options: QuizOption[] };

export type InterviewQuestion = {
  id: number;
  question: string;
  answer_md: string | null;
  difficulty: string;
};

export type ConceptDetail = ConceptSummary & {
  content_md: string;
  prerequisites: ConceptSummary[];
  unlocks: ConceptSummary[];
  resources: Resource[];
  quiz: QuizQuestion[];
  interview_questions: InterviewQuestion[];
  status: ProgressStatus | null;
  is_locked: boolean;
  missing_prerequisites: ConceptSummary[];
};

export type ProgressStatus = 'pending' | 'in-progress' | 'completed' | 'skipped';

export type Profile = {
  target_goal: string | null;
  current_track_id: number | null;
  current_track_slug: string | null;
  pace: string;
  daily_hours: number;
  target_date: string | null;
  xp: number;
  level: number;
  xp_into_level: number;
  xp_for_next_level: number;
  streak_days: number;
  longest_streak: number;
  last_active_on: string | null;
};

export type User = {
  id: number;
  email: string;
  display_name: string | null;
  profile: Profile;
};

export type RoadmapItem = {
  id: number;
  concept: ConceptSummary;
  week_no: number;
  status: ProgressStatus;
  is_locked: boolean;
  missing_prerequisites: string[];
};

export type RoadmapWeek = {
  week_no: number;
  title: string;
  total_hours: number;
  items: RoadmapItem[];
};

export type Roadmap = {
  id: number;
  track: TrackSummary;
  daily_hours: number;
  pace: string;
  created_at: string;
  total_concepts: number;
  completed_concepts: number;
  percent_complete: number;
  target_date: string | null;
  weeks: RoadmapWeek[];
};

/** A route in the switcher: everything but the week-by-week plan. */
export type RoadmapSummary = Omit<Roadmap, 'weeks'> & { is_focused: boolean };

export type Badge = {
  slug: string;
  name: string;
  description: string | null;
  icon: string;
  awarded_at: string;
};

export type CompletionResult = {
  concept_slug: string;
  quiz_score: number | null;
  passed: boolean;
  correct_count: number;
  question_count: number;
  xp_earned: number;
  total_xp: number;
  level: number;
  leveled_up: boolean;
  streak_days: number;
  new_badges: Badge[];
  unlocked_concepts: ConceptSummary[];
  review: QuizReview[];
};

export type QuizReview = {
  question_id: number;
  correct_option_id: number;
  selected_option_id: number | null;
  is_correct: boolean;
  explanation: string | null;
};

export type RoleReadiness = {
  slug: string;
  title: string;
  description: string | null;
  percent: number;
  earned_weight: number;
  total_weight: number;
};

export type MissingSkill = {
  concept: ConceptSummary;
  role_slug: string;
  percent_contribution: number;
  in_roadmap: boolean;
};

export type VelocityPoint = { day: string; minutes: number; concepts: number; xp: number };

export type Dashboard = {
  user: User;
  stats: {
    concepts_completed: number;
    concepts_total_in_track: number;
    hours_invested: number;
    xp: number;
    level: number;
    xp_into_level: number;
    xp_for_next_level: number;
    streak_days: number;
    longest_streak: number;
    active_days_30: number;
  };
  current_track: TrackSummary | null;
  roles: RoleReadiness[];
  missing_skills: MissingSkill[];
  velocity: VelocityPoint[];
  badges: Badge[];
  next_up: ConceptSummary[];
};

export type ChatSource = { slug: string; name: string };

export type ChatMessage = {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  degraded?: boolean;
  created_at?: string;
};

export type CommunityPost = {
  id: number;
  title: string;
  content: string;
  author: { id: number; display_name: string | null };
  domain: { slug: string; name: string } | null;
  upvotes: number;
  comment_count: number;
  created_at: string;
  viewer_has_voted: boolean;
};

export type CommunityComment = {
  id: number;
  content: string;
  author: { id: number; display_name: string | null };
  created_at: string;
};

/* --- points ledger ------------------------------------------------------ */

export type PointsEvent = {
  id: number;
  kind: 'concept' | 'project' | 'badge';
  ref_slug: string;
  label: string;
  points: number;
  created_at: string;
};

/* --- projects ----------------------------------------------------------- */

export type ProjectRuntime = 'python' | 'web' | 'sql';

export type ProjectFile = {
  path: string;
  content: string;
  is_readonly: boolean;
  is_entry: boolean;
};

export type ProjectTest = {
  id: number;
  name: string;
  kind: 'python-assert' | 'dom-assert' | 'sql-result';
  code: string;
  expected: string | null;
  is_hidden: boolean;
};

export type ProjectSummary = {
  id: number;
  slug: string;
  title: string;
  tagline: string;
  runtime: ProjectRuntime;
  difficulty: string;
  est_minutes: number;
  xp_reward: number;
  concept_slug: string;
  concept_name: string;
  status: 'passed' | 'failed' | null;
  best_passed: number;
};

export type ProjectDetail = ProjectSummary & {
  brief_md: string;
  concept: ConceptSummary;
  files: ProjectFile[];
  tests: ProjectTest[];
  solution_md: string | null;
  attempts: number;
};

export type ProjectSubmission = {
  id: number;
  passed_count: number;
  total_count: number;
  status: 'passed' | 'failed';
  xp_awarded: number;
  attempt_no: number;
  created_at: string;
};

export type SubmissionResult = {
  submission: ProjectSubmission;
  passed: boolean;
  rejected_reason: string | null;
  xp_earned: number;
  total_xp: number;
  level: number;
  leveled_up: boolean;
  new_badges: Badge[];
  solution_md: string | null;
};

/* --- companies ---------------------------------------------------------- */

export type CompanyResource = {
  id: number;
  kind: string;
  title: string;
  url: string;
};

export type CompanyRoleSummary = {
  id: number;
  slug: string;
  title: string;
  level: string;
  description: string | null;
  focus_count: number;
  question_count: number;
  readiness_percent: number | null;
};

export type CompanySummary = {
  id: number;
  slug: string;
  name: string;
  industry: string;
  hq: string | null;
  website: string | null;
  icon: string;
  description: string | null;
  fetched_on: string | null;
  role_count: number;
};

export type CompanyDetail = CompanySummary & {
  hiring_process_md: string | null;
  roles: CompanyRoleSummary[];
  resources: CompanyResource[];
  /** Member-submitted, unlike everything else on this object. */
  reviews: RatingSummary;
};

/* --- company reviews ----------------------------------------------------
 * Kept in their own block, and their own types, because they are a different
 * kind of claim from everything above: a company profile is researched and
 * source-cited, a review is one member's account of their own experience.
 * `kind: 'member-review'` rides along on every review so a component can never
 * render one as though it were sourced. */

export type ReviewOutcome =
  | 'offer'
  | 'rejected'
  | 'withdrew'
  | 'pending'
  | 'not-interviewed';

export type RatingSummary = {
  review_count: number;
  /** `null`, not 0, when nobody has reviewed yet. */
  average_rating: number | null;
  /** Star value ("1".."5") to how many reviews gave it. */
  distribution: Record<string, number>;
};

export type CompanyReview = {
  id: number;
  kind: 'member-review';
  company_slug: string;
  rating: number;
  title: string;
  body_md: string;
  interview_outcome: ReviewOutcome;
  interview_year: number | null;
  is_anonymous: boolean;
  /** Seeded demo content. The UI labels these so they cannot pass as real. */
  is_sample: boolean;
  author: { id: number | null; display_name: string | null };
  role: { slug: string; title: string } | null;
  helpful_count: number;
  not_helpful_count: number;
  created_at: string;
  updated_at: string;
  viewer_is_author: boolean;
  viewer_vote: number | null;
};

export type CompanyReviewList = {
  summary: RatingSummary;
  reviews: CompanyReview[];
  viewer_can_write: boolean;
  viewer_review_id: number | null;
};

export type FocusArea = {
  id: number;
  label: string;
  notes: string | null;
  weight: number;
  concept_slug: string | null;
  concept_name: string | null;
  is_completed: boolean;
  in_roadmap: boolean;
};

export type CompanyQuestionKind = 'interview' | 'exam' | 'online-assessment';

export type CompanyRound =
  | 'aptitude'
  | 'coding'
  | 'technical'
  | 'system-design'
  | 'managerial'
  | 'hr';

export type CompanyQuestion = {
  id: number;
  kind: CompanyQuestionKind;
  round: CompanyRound;
  topic: string | null;
  question: string;
  answer_md: string | null;
  difficulty: string;
  year: number | null;
  source_name: string;
  source_url: string;
};

export type CompanyRoleDetail = CompanyRoleSummary & {
  company: CompanySummary;
  focus_md: string | null;
  source_url: string | null;
  focus_areas: FocusArea[];
  questions: CompanyQuestion[];
  readiness_percent: number;
  covered_weight: number;
  total_weight: number;
};
