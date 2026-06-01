const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/logistica";

// Contrato do Portal B2B: portal pai abre este MS com ?jwt=<token> na URL.
// Lemos a query string, gravamos em sessionStorage["portal_b2b_jwt"] e limpamos a URL.
// A partir dai, toda chamada ao back vai com Authorization: Bearer <token>.
const TOKEN_STORAGE_KEY = "portal_b2b_jwt";

function readTokenFromQueryString() {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("jwt");
}

function stripTokenFromUrl() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (!url.searchParams.has("jwt")) return;
  url.searchParams.delete("jwt");
  window.history.replaceState({}, document.title, url.toString());
}

export function bootstrapAuthToken() {
  const fromQuery = readTokenFromQueryString();
  if (fromQuery) {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, fromQuery);
    stripTokenFromUrl();
  }
}

export function getAuthToken() {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // Token invalido/expirado/ausente -> descarta sessao local.
    // Quem chamou o MS de logistica (o portal pai) que decide o que fazer dai.
    clearAuthToken();
  }

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
