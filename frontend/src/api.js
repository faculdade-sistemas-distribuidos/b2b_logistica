const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/logistica";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),

  criarDemo: (dados) =>
    request("/demo-fluxo-completo", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  listarSolicitacoes: () => request("/solicitacoes"),

  detalharSolicitacao: (id) => request(`/solicitacoes/${id}`),

  listarCotacoes: (solicitacaoId) =>
    request(`/solicitacoes/${solicitacaoId}/cotacoes`),
};
