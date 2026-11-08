const configuredBase = import.meta.env?.VITE_API_BASE_URL?.trim();
const API_BASE = configuredBase || "/api";

function buildUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiRequest(path, { token, method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let requestBody;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    requestBody = form instanceof URLSearchParams ? form : new URLSearchParams(form);
  } else if (body !== undefined) {
    if (typeof FormData !== "undefined" && body instanceof FormData) {
      // Let the browser set the multipart boundary for file uploads.
      requestBody = body;
    } else {
      headers["Content-Type"] = "application/json";
      requestBody = JSON.stringify(body);
    }
  }

  const response = await fetch(buildUrl(path), {
    method,
    headers,
    body: requestBody,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    let message = "Request failed";
    if (typeof payload === "string" && payload) message = payload;
    else if (payload?.detail) {
      message = typeof payload.detail === "string"
        ? payload.detail
        : payload.detail.message || JSON.stringify(payload.detail);
    } else if (payload?.message) message = payload.message;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export function formatDate(value, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function moneyLabel(value) {
  if (value === null || value === undefined || value === "") return "Package not specified";
  return String(value);
}

export function statusClass(status = "") {
  const value = status.toLowerCase();
  if (["selected", "offer accepted", "joined", "pass", "present", "completed"].includes(value)) return "success";
  if (["rejected", "withdrawn", "fail", "absent", "cancelled"].includes(value)) return "danger";
  if (["shortlisted", "in progress", "under review", "offer released", "scheduled", "on hold"].includes(value)) return "warning";
  return "neutral";
}


export async function apiBlobRequest(path, { token } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(buildUrl(path), { headers });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    const message = typeof payload === "string" ? payload : payload?.detail || payload?.message || "Unable to download file";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return response.blob();
}
