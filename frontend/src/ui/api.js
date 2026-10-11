const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export async function request(path, options = {}) {
  const token = localStorage.getItem('flowsync_token');
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Preserve the HTTP error when the response isn't JSON.
    }
    throw new Error(detail);
  }
  return response;
}

export async function getJson(path) {
  return (await request(path)).json();
}

export async function postJson(path, body) {
  return (await request(path, { method: 'POST', body: JSON.stringify(body) })).json();
}

export { API };
