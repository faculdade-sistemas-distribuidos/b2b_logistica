import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "./api.js";
import Header from "./components/Header.jsx";
import SolicitacaoForm from "./components/SolicitacaoForm.jsx";
import SolicitacaoCard from "./components/SolicitacaoCard.jsx";

export default function App() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("theme");
    return saved ? saved === "dark" : true;
  });
  const [health, setHealth] = useState(null);
  const [solicitacoes, setSolicitacoes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const detailCache = useRef({});

  // Dark mode
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // Health check
  useEffect(() => {
    const check = () =>
      api.health().then(() => setHealth(true)).catch(() => setHealth(false));
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);

  // Fetch list
  const fetchList = useCallback(async () => {
    try {
      const list = await api.listarSolicitacoes();
      // enrich with details from cache
      const enriched = list.map((s) => detailCache.current[s.id] || s);
      setSolicitacoes(enriched);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchList();
    const id = setInterval(fetchList, 8000);
    return () => clearInterval(id);
  }, [fetchList]);

  // Poll active solicitations for detail
  useEffect(() => {
    const active = solicitacoes.filter(
      (s) => s.status !== "ENTREGUE"
    );
    if (active.length === 0) return;

    const poll = async () => {
      for (const s of active) {
        try {
          const detail = await api.detalharSolicitacao(s.id);
          detailCache.current[s.id] = detail;
          setSolicitacoes((prev) =>
            prev.map((x) => (x.id === detail.id ? detail : x))
          );
        } catch { /* silent */ }
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [solicitacoes.map((s) => `${s.id}:${s.status}`).join(",")]);

  // Create demo
  const handleCreate = async (dados) => {
    setLoading(true);
    try {
      const created = await api.criarDemo(dados);
      detailCache.current[created.id] = created;
      setSolicitacoes((prev) => [created, ...prev]);
      setFormOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const activeCount = solicitacoes.filter((s) => s.status !== "ENTREGUE").length;

  return (
    <div className="min-h-screen transition-colors duration-300">
      <Header dark={dark} setDark={setDark} health={health} />

      <main className="mx-auto max-w-7xl px-4 pb-12 pt-6 sm:px-6 lg:px-8">
        {/* Actions bar */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
              Painel de Monitoramento
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {solicitacoes.length} solicitação(ões) •{" "}
              <span className="text-brand-400 font-semibold">{activeCount} ativa(s)</span>
            </p>
          </div>
          <button className="btn-primary" onClick={() => setFormOpen(!formOpen)}>
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            {formOpen ? "Fechar Formulário" : "Nova Solicitação Demo"}
          </button>
        </div>

        {/* Form */}
        {formOpen && (
          <div className="animate-slide-up mb-8">
            <SolicitacaoForm onSubmit={handleCreate} loading={loading} />
          </div>
        )}

        {/* Empty state */}
        {solicitacoes.length === 0 && (
          <div className="card flex flex-col items-center justify-center py-20 text-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="mb-4 h-16 w-16 text-gray-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <h3 className="text-lg font-semibold text-gray-600 dark:text-gray-300">
              Nenhuma solicitação encontrada
            </h3>
            <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
              Clique em "Nova Solicitação Demo" para iniciar o fluxo
            </p>
          </div>
        )}

        {/* Grid */}
        <div className="grid gap-6 grid-cols-1 md:grid-cols-2 max-h-[800px] overflow-y-auto pr-2 pb-4">
          {solicitacoes.map((s) => (
            <SolicitacaoCard key={s.id} solicitacao={s} />
          ))}
        </div>
      </main>
    </div>
  );
}
