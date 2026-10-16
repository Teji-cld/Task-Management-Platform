// All communication with the backend lives in this file.
// The path is RELATIVE ("/api"), so the browser sends requests to whatever
// host served the page: the Vite dev server in development, a reverse proxy
// in production. Nothing here knows about hostnames or ports.
const API_BASE = "/api";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorMessage(response) {
  // FastAPI errors are JSON like {"detail": "Task not found"}.
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).join(". ");
    }
  } catch {
    // The body was not JSON (for example an HTML error page from a proxy).
  }
  if (response.status >= 502 && response.status <= 504) {
    return "The server is unavailable right now. Try again in a moment.";
  }
  return `Request failed (status ${response.status}).`;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }
  if (response.status === 204) return null; // DELETE returns no body
  return response.json();
}

export const listTasks = () => request("/tasks");

export const createTask = (task) =>
  request("/tasks", { method: "POST", body: JSON.stringify(task) });

// PUT replaces the whole task, so send title, description and completed together.
export const updateTask = (id, task) =>
  request(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(task) });

export const deleteTask = (id) => request(`/tasks/${id}`, { method: "DELETE" });
