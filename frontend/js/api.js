async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  return body;
}
export const api = {
  dashboard: () => request("/api/dashboard"),
  documents: (offset) => request(`/api/documents?limit=20&offset=${offset}`),
  document: (id) => request(`/api/documents/${id}`),
  remove: (id) => request(`/api/documents/${id}`, { method: "DELETE" }),
  model: () => request("/api/system/model"),
  taxonomy: () => request("/api/system/taxonomy"),
  analyze: (file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/api/analyze", { method: "POST", body });
  },
};
