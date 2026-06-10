const API_BASE = "/api/logistica";

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

// --- INÍCIO DA CAMADA DE MOCK (ISOLAMENTO DA DEMO) ---
const mockDb = {
  solicitacoes: [], // Armazena apenas solicitações geradas pela Demo
};

function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-HTTPS environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function simulateDelay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
// --- FIM DA CAMADA DE MOCK ---

export const api = {
  health: () => request("/health"),

  // Etapa 1: cria solicitação e gera cotações → para em COTADO
  iniciarCotacao: async (dados) => {
    console.log("🛠️ [MOCK] Interceptando iniciarCotacao", dados);
    await simulateDelay(800); // simula rede

    const id = generateUUID();
    const mockSolicitacao = {
      id,
      pedido_id: dados.pedido_id,
      tipo_transporte: dados.tipo_transporte || "RODOVIARIO",
      status: "AGUARDANDO",
      data_criacao: new Date().toISOString(),
      isMock: true, // flag interna para saber que é mock
      cotacoes: [],
    };

    mockDb.solicitacoes.push(mockSolicitacao);

    // Simula a background task gerando 3 cotações
    setTimeout(() => {
      console.log(`🛠️ [MOCK] Gerando cotações para ${id}...`);
      const transportadoras = ["TransLog Express", "Rodo Frete Brasil", "CargoVia Sul"];
      mockSolicitacao.cotacoes = transportadoras.map((nome) => ({
        id: generateUUID(),
        transportadora_id: generateUUID(),
        transportadora: { id: generateUUID(), nome_fantasia: nome },
        valor: (Math.random() * 1500 + 500).toFixed(2),
        prazo: Math.floor(Math.random() * 10) + 2,
      }));
      mockSolicitacao.status = "COTADO";
    }, 2000);

    return mockSolicitacao;
  },

  // Etapa 2: confirma a cotação escolhida → dispara SELECIONADO → EM_TRANSITO → ENTREGUE
  contratarFrete: async (solicitacaoId, cotacaoId) => {
    console.log("🛠️ [MOCK] Interceptando contratarFrete", solicitacaoId, cotacaoId);
    await simulateDelay(500);

    const sol = mockDb.solicitacoes.find(s => s.id === solicitacaoId);
    if (!sol) {
      // Se não achar no mock, repassa pro backend real (caso seja teste na base oficial)
      return request("/demo-contratar-frete", {
        method: "POST",
        body: JSON.stringify({ solicitacao_id: solicitacaoId, cotacao_id: cotacaoId }),
      });
    }

    const cotacao = sol.cotacoes.find(c => c.id === cotacaoId);
    if (!cotacao) throw new Error("Cotação mock não encontrada");

    sol.status = "SELECIONADO";
    sol.frete_selecionado = {
      id: generateUUID(),
      cotacao_id: cotacaoId,
      cotacao: cotacao,
    };

    // Progressão automática de status em background
    setTimeout(() => {
      if (sol.status === "SELECIONADO") sol.status = "EM_TRANSITO";
      console.log(`🚚 [MOCK] Status atualizado: ${sol.id} → EM_TRANSITO`);
      
      setTimeout(() => {
        if (sol.status === "EM_TRANSITO") sol.status = "ENTREGUE";
        console.log(`📦 [MOCK] Status atualizado: ${sol.id} → ENTREGUE`);
      }, 10000); // +10s para ENTREGUE
    }, 5000); // 5s para EM_TRANSITO

    return sol;
  },

  listarSolicitacoes: async () => {
    // Busca do backend real
    const realData = await request("/solicitacoes").catch(() => []);
    
    // Mescla mock + real
    const merged = [...mockDb.solicitacoes, ...realData];
    
    // Ordena por data decrescente
    merged.sort((a, b) => new Date(b.data_criacao) - new Date(a.data_criacao));
    return merged;
  },

  detalharSolicitacao: async (id) => {
    const sol = mockDb.solicitacoes.find(s => s.id === id);
    if (sol) {
      await simulateDelay(300);
      return sol; // Retorna do mock
    }
    // Se não for mock, busca do real
    return request(`/solicitacoes/${id}`);
  },

  listarCotacoes: async (solicitacaoId) => {
    const sol = mockDb.solicitacoes.find(s => s.id === solicitacaoId);
    if (sol) {
      await simulateDelay(200);
      return sol.cotacoes || [];
    }
    return request(`/solicitacoes/${solicitacaoId}/cotacoes`);
  },
};
