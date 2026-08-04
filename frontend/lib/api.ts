// Cliente de la API del backend. El token (A5) vive en localStorage y viaja
// como Bearer; para <audio src> y QR va en query (?token=).

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("lyp_token") ?? "";
}

export function setToken(t: string) {
  localStorage.setItem("lyp_token", t);
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
  });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok && res.status !== 202) throw new Error(`API ${res.status}`);
  return res.json() as Promise<T>;
}

export function mediaUrl(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
  const tok = getToken();
  return `${API_BASE}${path}${tok ? `${sep}token=${encodeURIComponent(tok)}` : ""}`;
}

export function wsUrl(docId: number): string {
  const base = API_BASE.replace(/^http/, "ws");
  const tok = getToken();
  return `${base}/ws?doc=${docId}${tok ? `&token=${encodeURIComponent(tok)}` : ""}`;
}

export interface DocSummary {
  id: number;
  title: string;
  status: string;
  language: string;
  blocks: number;
  blocks_done: number;
  position_idx: number | null;
  total_cost_cents: number;
  rss_published_at: string | null;
  full_mp3_path: string | null;
}

export interface Block {
  id: number;
  section_id: number;
  idx: number;
  audio_status: string;
  duration_ms: number | null;
  page: number;
  preview: string;
}

export interface DocDetail extends DocSummary {
  sections: { id: number; idx: number; title: string }[];
  playlist: Block[];
  position: { block_id: number; offset_ms: number } | null;
}
