export interface UserUpsertRequest {
  user_id: string;
  username?: string;
  first_name?: string;
  middle_name?: string;
  last_name?: string;
  native_language?: string;
  base_language?: string;
  target_language?: string;
  current_level?: string;
  city?: string;
  profile_summary?: string;
}

export interface UserUpsertResponse {
  user_id: string;
  created: boolean;
}

export interface UserVerifyResponse {
  exists: boolean;
  user_id?: string;
  username?: string;
  first_name?: string;
  base_language?: string;
  target_language?: string;
  current_level?: string;
  city?: string;
}

export interface ContextScenario {
  location?: string;
  environment?: string;
  sentiment?: string;
  intent?: string;
}

export interface RecommendationGenerateRequest {
  user_id: string;
  original_text: string;
  translation?: string;
  source_language: string;
  target_language: string;
  context_scenario?: ContextScenario;
}

export interface RecommendationItem {
  text: string;
  score: number;
  reason?: string;
  usage?: string;
}

export interface RecommendationMetadata {
  attempts: number;
  duration_ms: number;
}

export interface RecommendationGenerateResponse {
  translation: string;
  recommendations: RecommendationItem[];
  metadata: RecommendationMetadata;
}

// Legacy types (kept for backward compatibility if needed)
export interface ContextualAction {
  original_text: string;
  translation: string | null;
  source_language: string;
  target_language: string;
  context: {
    location?: string;
    environment?: string;
    sentiment?: string;
    intent?: string;
    tense?: string;
    topic?: string;
  };
}

export interface ContextualRecommendationRequest {
  user_id: string;
  action: ContextualAction;
}

export interface RecommendationExplanation {
  fusion?: number;
  vector?: number;
  lexical?: number;
}

export interface PracticeExercise {
  type: string;
  prompt: string;
  options: string[];
  correct_answer?: string | null;
  explanation?: string | null;
}

export interface PracticeResponse {
  context_theme: string;
  exercises: PracticeExercise[];
}

export interface ContextualRecommendationResponse {
  translation: string;
  recommendations: RecommendationItem[];
}

function parseDebugBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") {
    return body ?? null;
  }

  try {
    return JSON.parse(body) as unknown;
  } catch {
    return body;
  }
}

let API_BASE_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, "");

if (
  !API_BASE_URL ||
  (API_BASE_URL.includes("localhost") &&
    window.location.hostname !== "localhost")
) {
  API_BASE_URL = `http://${window.location.hostname}:8000`;
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const method = init.method ?? "GET";
  console.debug("[api] request", {
    method,
    path,
    url: `${API_BASE_URL}${path}`,
    body: parseDebugBody(init.body),
  });

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const bodyText = await response.text();
    console.error("[api] response error", {
      method,
      path,
      status: response.status,
      body: bodyText,
    });
    throw new Error(bodyText || `Request failed (${response.status})`);
  }

  const data = (await response.json()) as T;
  console.debug("[api] response", {
    method,
    path,
    status: response.status,
    data,
  });
  return data;
}

export async function upsertUser(
  payload: UserUpsertRequest,
): Promise<UserUpsertResponse> {
  return apiRequest<UserUpsertResponse>("/api/v1/users/upsert", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyUser(name: string): Promise<UserVerifyResponse> {
  return apiRequest<UserVerifyResponse>("/api/v1/users/verify", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function generateRecommendations(
  payload: RecommendationGenerateRequest,
): Promise<RecommendationGenerateResponse> {
  return apiRequest<RecommendationGenerateResponse>(
    "/api/v1/recommendations/generate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

// Legacy function - kept for backward compatibility
export async function requestContextualRecommendations(
  payload: ContextualRecommendationRequest,
): Promise<ContextualRecommendationResponse> {
  return apiRequest<ContextualRecommendationResponse>(
    "/api/v1/recommendations/contextual",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function requestPractice(
  userId: string,
  limit = 6,
): Promise<PracticeResponse> {
  const query = new URLSearchParams({ user_id: userId, limit: String(limit) });
  return apiRequest<PracticeResponse>(
    `/api/v1/practice/generate?${query.toString()}`,
    {
      method: "GET",
    },
  );
}

export async function requestTranslation(payload: {
  original_text: string;
  source_language: string;
  target_language: string;
  user_level: string;
}): Promise<{ translation: string }> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/recommendations/translate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to fetch translation.");
  }

  return response.json();
}

export interface PracticeGenerateRequest {
  user_id: string;
  exercise_type: string;
  original_text: string;
  translation: string;
  source_language: string;
  target_language: string;
  current_level: string;
  context_label: string;
  recommendations: string[];
}

export async function generatePracticeExercise(
  payload: PracticeGenerateRequest,
): Promise<PracticeExercise> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/practice/generate-exercise`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to generate practice exercise.");
  }
  return response.json();
}
