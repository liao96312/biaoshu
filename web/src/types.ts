export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  request_id: string;
  timestamp: number;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

export type Severity = "high" | "medium" | "low";
export type ReviewStatus = "pending" | "confirmed" | "dismissed" | "modified" | "approved";
export type DeviationType = "positive" | "none" | "negative" | "unknown";

export interface ProjectCounts {
  high?: number;
  medium?: number;
  low?: number;
  [key: string]: number | undefined;
}

export interface Project {
  id: string;
  name: string;
  tender_name: string;
  company_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  risk_count?: ProjectCounts;
  deviation_count?: Record<string, number>;
  tech_param_count?: number;
}

export interface ReviewSummary {
  blocker_count: number;
  high_risk_count?: number;
  negative_deviation_count?: number;
  pending_feedback_count?: number;
  [key: string]: unknown;
}

export interface RiskItem {
  id: string;
  risk_type: string;
  requirement: string;
  trigger_keyword: string;
  severity: Severity;
  need_material: boolean;
  source_page?: number | null;
  source_section?: string | null;
  source_text: string;
  ai_reason: string;
  suggestion: string;
  confidence: number;
  status: ReviewStatus;
  reviewer_note?: string | null;
  material_ids: string[];
}

export interface ClauseItem {
  id?: string;
  clause_type: string;
  clause_text: string;
  keywords?: string[];
  source_section?: string;
  file_name?: string;
  source_page?: number | null;
}

export interface DeviationResult {
  id: string;
  item: string;
  parameter: string;
  required_value: string;
  our_value?: string | null;
  deviation_type: DeviationType;
  response_text: string;
  evidence?: string | null;
  source_page?: number | null;
  confidence: number;
  reviewer_status: ReviewStatus;
}

export interface MaterialRecommendation {
  material_id: string;
  name?: string;
  file_name?: string;
  score: number;
  reason?: string;
}

export interface RecommendationGroup {
  risk_id: string;
  recommendations: MaterialRecommendation[];
}

export interface MaterialGap {
  risk_id: string;
  severity: Severity;
  material_requirement: string;
  suggestion: string;
  bound_materials?: string[];
  source_page?: number | null;
  status: string;
}

export interface ScoringRow {
  score_point: string;
  requirement: string;
  response: string;
  evidence?: string;
  priority: string;
}

export interface OutlineItem {
  title: string;
  status: string;
}

export interface OutlineSection {
  code: string;
  title: string;
  items: OutlineItem[];
}

export interface DocumentItem {
  id: string;
  file_name: string;
  file_type: string;
  parse_status: string;
  page_count: number;
}

export interface TaskItem {
  id: string;
  task_type: string;
  status: string;
  progress: number;
  current_step: string;
  error_message?: string | null;
}

export interface Material {
  id: string;
  file_name: string;
  material_type: string;
  name?: string | null;
  tags: string[];
  page_count: number;
}

export interface Feedback {
  id: string;
  target_type: string;
  target_id: string;
  action: string;
  reviewer_note?: string | null;
  created_at: string;
}

export interface ActivityLog {
  id: string;
  actor: string;
  method: string;
  path: string;
  status_code: number;
  project_id?: string | null;
  action: string;
  created_at: string;
}

export interface ExportCreated {
  export_id: string;
  task_id: string;
}
