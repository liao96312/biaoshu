import type { ApiEnvelope, ExportCreated } from "./types";

const authToken = () => localStorage.getItem("bidAgentToken")?.trim();
const companyTenant = () => localStorage.getItem("bidAgentCompanyId")?.trim();

export function setCompanyTenant(companyId: string) {
  const value = companyId.trim();
  if (value) {
    localStorage.setItem("bidAgentCompanyId", value);
  } else {
    localStorage.removeItem("bidAgentCompanyId");
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = authToken();
  const tenant = companyTenant();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (tenant) {
    headers.set("X-Company-ID", tenant);
  }

  const response = await fetch(path, {
    ...options,
    headers
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? ((await response.json()) as ApiEnvelope<T>)
    : ({ code: response.ok ? 0 : response.status, message: response.statusText, data: null } as ApiEnvelope<T>);

  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || "请求失败");
  }

  return payload.data;
}

export function uploadTender(projectId: string, file: File) {
  const form = new FormData();
  form.append("doc_type", "tender");
  form.append("file", file);
  return api<{ document_id: string; parse_task_id: string }>(`/api/v1/projects/${projectId}/documents`, {
    method: "POST",
    body: form
  });
}

export function uploadMaterial(companyId: string, file: File, materialType = "product") {
  const form = new FormData();
  form.append("material_type", materialType);
  form.append("name", file.name);
  form.append("file", file);
  return api<{ material_id: string }>(`/api/v1/companies/${companyId}/materials`, {
    method: "POST",
    body: form
  });
}

export async function createExport(projectId: string, payload: { export_type: string; format: string; options?: Record<string, unknown> }) {
  const created = await api<ExportCreated>(`/api/v1/projects/${projectId}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  window.location.href = `/api/v1/exports/${created.export_id}/download`;
}

export function taskSocket(taskId: string) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const token = authToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return new WebSocket(`${protocol}://${window.location.host}/ws/tasks/${taskId}${query}`);
}
