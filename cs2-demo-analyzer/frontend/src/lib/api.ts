// Типы ответа backend (см. backend/analysis/*) и запросы к API.

export type Category = "perfect" | "slow" | "moving" | "air";
export type Timing = "good" | "early" | "late";
export type Technique = "counter" | "release" | "none";

export interface ApiErrorBody {
  code: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export interface PlayerRow {
  steamid: string;
  name: string;
  team: number;
  kills: number;
  deaths: number;
  report_id?: string;
}

export interface MatchMeta {
  map: string;
  rounds: number;
  server?: string;
  tickrate: number;
  score: { t: number; ct: number };
}

export interface MatchStatus {
  id: string;
  status: "queued" | "processing" | "done" | "failed";
  progress: number;
  stage: string;
  filename: string;
  error: ApiErrorBody | null;
  match: MatchMeta | null;
  players: PlayerRow[];
}

export interface CsShot {
  tick: number;
  round: number | null;
  round_time: number | null;
  weapon: string;
  weapon_name: string;
  speed: number;
  threshold: number;
  speed_ratio: number;
  category: Category;
  context: "strafe" | "stationary";
  technique: Technique | null;
  timing: Timing | null;
  brake_to_shot_ticks: number | null;
  stop_to_shot_ticks: number | null;
}

export interface WeaponRow {
  weapon: string;
  weapon_name: string;
  first_shots: number;
  strafe_shots: number;
  perfect_pct: number | null;
  accurate_pct: number | null;
  moving_pct: number | null;
  median_speed: number;
}

export interface Counterstrafe {
  buttons_available: boolean;
  accuracy_speed_ratio?: number;
  first_shots: number;
  strafe_shots: number;
  perfect_pct: number | null;
  accurate_pct: number | null;
  categories: Record<Category, number>;
  strafe_categories: Record<Category, number>;
  timing: Partial<Record<Timing, number>>;
  timing_pct?: Partial<Record<Timing, number>>;
  technique: Partial<Record<Technique, number>>;
  technique_pct?: Partial<Record<Technique, number>>;
  median_brake_to_shot_ms: number | null;
  by_weapon: WeaponRow[];
  speed_histogram: ({ bin: string } & Record<Category, number>)[];
  shots: CsShot[];
  worst: Pick<CsShot, "round" | "tick" | "round_time" | "weapon_name" | "speed" | "category" | "timing">[];
}

export interface WinRate {
  count: number;
  wins: number;
  winrate: number | null;
}

export interface Duel {
  round: number;
  start_tick: number;
  kill_tick: number | null;
  opponent_name: string;
  result: "win" | "loss" | "none";
  opening: boolean;
  shot_first: boolean | null;
  damaged_first: boolean;
  ttk_ms: number | null;
  dmg_dealt: number;
  dmg_taken: number;
  flash_support: boolean;
  got_flashed: boolean;
  peeked: boolean | null;
  distance: number | null;
  headshot: boolean | null;
}

export interface Duels {
  total: number;
  decided: number;
  wins: number;
  losses: number;
  winrate: number | null;
  opening?: WinRate;
  shot_first_pct?: number | null;
  when_shot_first?: WinRate;
  when_shot_second?: WinRate;
  median_ttk_ms?: number | null;
  peek_with_flash?: WinRate;
  peek_without_flash?: WinRate;
  holding?: WinRate;
  by_round: { round: number; wins: number; losses: number; none: number }[];
  duels: Duel[];
  worst: Duel[];
  approximations?: string[];
}

export interface CrosshairEvent {
  round: number | null;
  tick: number;
  round_time: number | null;
  enemy: string;
  angle: number;
  yaw_err: number;
  pitch_err: number;
  distance: number;
}

export interface Crosshair {
  approximate: boolean;
  method: string;
  samples: number;
  front_samples?: number;
  median_angle: number | null;
  mean_angle?: number | null;
  good_pct?: number | null;
  median_abs_yaw_err?: number | null;
  median_pitch_err?: number | null;
  histogram: { bin: string; count: number }[];
  worst: CrosshairEvent[];
}

export interface Recommendation {
  id: string;
  kind: "improve" | "stop";
  category: string;
  severity: number;
  priority: number;
  value: number;
  threshold: number;
  samples: number;
  title: string;
  text: string;
}

export interface Rating {
  elo: number;
  elo_low: number;
  elo_high: number;
  level: number;
  level_low: number;
  level_high: number;
  calibrated: boolean;
  model_version: string;
  missing_features: string[];
  disclaimer: string;
}

export interface FaceitAccount {
  player_id: string | null;
  nickname: string | null;
  avatar: string | null;
  url: string | null;
  country: string | null;
  elo: number | null;
  level: number | null;
}

export interface FaceitAdjustment {
  tier: "very_bad" | "bad" | "normal";
  perf: number;
  match_elo: number;
  current_elo: number;
  current_level: number;
  delta: number;
  tier_delta_min: number;
  tier_delta_max: number;
  new_elo: number;
  new_level: number;
  reasons: string[];
  disclaimer: string;
}

export interface FaceitBlock {
  status: "found" | "not_found" | "unavailable" | "no_key";
  account: FaceitAccount | null;
  message: string | null;
  checked_at: number;
  adjustment: FaceitAdjustment | null;
}

export interface Report {
  version: number;
  faceit?: FaceitBlock;
  player: { steamid: string; name: string };
  match: MatchMeta;
  overview: {
    rounds: number;
    kills: number;
    deaths: number;
    hs_pct: number | null;
    kd: number;
    kpr: number;
    adr: number;
  };
  counterstrafe: Counterstrafe;
  accuracy: {
    shots: number;
    hits: number;
    accuracy_pct: number | null;
    first_bullets: number;
    first_bullet_hits: number;
    first_bullet_accuracy_pct: number | null;
    head_hit_pct: number | null;
  };
  duels: Duels;
  crosshair: Crosshair;
  trades: {
    deaths: number;
    traded_deaths: number;
    traded_pct: number | null;
    kills: number;
    trade_kills: number;
    trade_kill_pct: number | null;
  };
  recommendations: { items: Recommendation[]; top: Recommendation[]; improve: Recommendation[]; stop: Recommendation[] };
  rating: Rating;
}

export interface ReportResponse {
  id: string;
  match_id: string;
  created_at: string;
  players: PlayerRow[];
  report: Report;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let code = "http_error";
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail?.code) {
        code = body.detail.code;
        message = body.detail.message;
      }
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => request<{ max_upload_mb: number; chunk_size: number }>("/api/config"),
  createUpload: (filename: string, size: number) =>
    request<{ upload_id: string; chunk_size: number; total_chunks: number }>("/api/uploads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, size }),
    }),
  putChunk: (uploadId: string, index: number, chunk: Blob) =>
    request<{ ok: boolean }>(`/api/uploads/${uploadId}/chunks/${index}`, {
      method: "PUT",
      headers: { "Content-Type": "application/octet-stream" },
      body: chunk,
    }),
  complete: (uploadId: string) =>
    request<{ match_id: string }>(`/api/uploads/${uploadId}/complete`, { method: "POST" }),
  match: (id: string) => request<MatchStatus>(`/api/matches/${id}`, { cache: "no-store" }),
  report: (id: string) => request<ReportResponse>(`/api/reports/${id}`),
  refreshFaceit: (id: string) => request<FaceitBlock>(`/api/reports/${id}/faceit/refresh`, { method: "POST" }),
};
