// types/index.ts
// All shared TypeScript interfaces for Debug Dojo frontend

export type Difficulty = "Easy" | "Medium" | "Hard";
export type Outcome = "passed" | "failed" | "error" | "timeout";

// ── Challenge ──────────────────────────────────────────────────────────────

export interface VisibleTestCase {
  id: string;
  input_args: unknown[];
  expected_output: unknown;
  is_hidden: false;
}

export interface Challenge {
  id: string;
  title: string;
  description: string;
  difficulty: Difficulty;
  starter_code: string;
  function_signature: string;
  concept_tags: string[];
  xp_reward: number;
  time_limit_seconds: number;
  visible_test_cases: VisibleTestCase[];
}

// ── Submission ─────────────────────────────────────────────────────────────

export interface TestCaseResult {
  test_id: string;
  outcome: Outcome;
  is_hidden: boolean;
  actual_output: string | null;
  stdout: string | null;
  elapsed_ms: number | null;
  error_message: string | null;
  limit_hit: string | null;
}

export interface Explanation {
  summary: string;
  body: string;
  failed_visible_count: number;
  failed_hidden_count: number;
  llm_used: boolean;
}

export interface RecurringTag {
  tag: string;
  occurrences: number;
  previous_challenge_ids: string[];
  suggested_challenge_id: string | null;
  suggested_challenge_title: string | null;
  suggested_challenge_difficulty: string | null;
}

export interface RecurringResult {
  has_recurring: boolean;
  recurring_tags: RecurringTag[];
  non_recurring_tags: string[];
}

export interface MasteryUpdate {
  concept_tag: string;
  previous_score: number;
  new_score: number;
  delta: number;
  action: "increased" | "decreased" | "unchanged";
  hints_weight_applied: number | null;
}

export interface SubmissionResponse {
  submission_id: string;
  outcome: Outcome;
  passed_tests: number;
  total_tests: number;
  test_results: TestCaseResult[];
  explanation: Explanation;
  hint_ladder: null;
  mistake_tags: string[];
  recurring: RecurringResult;
  mastery_updates: MasteryUpdate[];
  xp_awarded: number;
  new_total_xp: number;
  execution_ms: number | null;
}

// ── Hints ──────────────────────────────────────────────────────────────────

export interface HintResponse {
  submission_id: string;
  hint_1: string | null;
  hint_2: string | null;
  hint_3: string | null;
  cached: boolean;
  llm_used: boolean;
  message?: string;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface LearnerProfile {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  xp_points: number;
  streak_days: number;
  last_active_date: string | null;
}

export interface MasteryRecord {
  id: string;
  learner_id: string;
  concept_tag: string;
  mastery_score: number;
  attempts: number;
  correct_attempts: number;
  last_attempted_at: string | null;
}

export interface RecentSubmission {
  id: string;
  challenge_id: string;
  outcome: Outcome;
  passed_tests: number;
  total_tests: number;
  xp_awarded: number;
  submitted_at: string;
}

export interface DashboardData {
  learner: LearnerProfile;
  stats: {
    total_submissions: number;
    passed_submissions: number;
    pass_rate: number;
    streak_days: number;
    xp_points: number;
  };
  mastery: MasteryRecord[];
  weakest_topics: string[];
  recent_submissions: RecentSubmission[];
}
