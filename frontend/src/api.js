const API_BASE = import.meta.env.VITE_API_BASE_URL || (window.location.hostname === "localhost" ? "http://localhost:5008" : "/api/logistica");

// ============================================================
// Auth Bootstrap — Portal B2B (PR #1 — rrosantos)
//
// Contrato: o portal pai abre este MS com ?jwt=<token> na URL.
// Lemos a query string, gravamos em sessionStorage e limpamos a URL.
// A partir daí, toda chamada ao back vai com Authorization: Bearer <token>.
// ============================================================
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

/** Deve ser chamado ANTES do primeiro render (ver main.jsx). */
export function bootstrapAuthToken() {
  const fromQuery = readTokenFromQueryString();
  if (fromQuery) {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, fromQuery);
    stripTokenFromUrl();
  } else if (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
    const MOCK_JWT = "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAiMTIzNDU2Nzg5MCIsICJuYW1lIjogIkpvaG4gRG9lIiwgImlhdCI6IDE1MTYyMzkwMjJ9.3Zlhc3lvuD07LyAmvIjkVa_Dg-Gvxqs7Gv4DOqrcr2M";
    if (!sessionStorage.getItem(TOKEN_STORAGE_KEY)) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, MOCK_JWT);
      console.warn("🔐 MOCK JWT injetado no sessionStorage para desenvolvimento local.");
    }
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

// ============================================================
// HTTP Client
// ============================================================
async function request(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    "Content-Type": "application/json",
    // Injeta Bearer se houver token na sessão
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // Token inválido/expirado/ausente → descarta sessão local.
    // O portal pai é responsável por reautenticar o usuário.
    clearAuthToken();
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ============================================================
// API Surface — Fluxo descentralizado (Etapa 1 + Etapa 2)
// ============================================================
export const api = {
  health: () => request("/health"),

  // Etapa 1: cria solicitação e gera cotações → para em COTADO
  iniciarCotacao: (dados) =>
    request("/demo-iniciar-cotacao", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  // Etapa 2: confirma a cotação escolhida → dispara SELECIONADO → EM_TRANSITO → ENTREGUE
  contratarFrete: (solicitacaoId, cotacaoId) =>
    request("/demo-contratar-frete", {
      method: "POST",
      body: JSON.stringify({ solicitacao_id: solicitacaoId, cotacao_id: cotacaoId }),
    }),

  listarSolicitacoes: () => request("/solicitacoes"),

  detalharSolicitacao: (id) => request(`/solicitacoes/${id}`),

  listarCotacoes: (solicitacaoId) =>
    request(`/solicitacoes/${solicitacaoId}/cotacoes`),
};
