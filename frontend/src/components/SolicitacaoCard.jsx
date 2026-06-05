import { useState } from "react";
import { api } from "../api.js";
import StatusPipeline from "./StatusPipeline.jsx";

const STATUS_COLORS = {
  AGUARDANDO: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
  COTADO:     "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400",
  SELECIONADO:"bg-brand-100 text-brand-700 dark:bg-brand-400/15 dark:text-brand-400",
  EM_TRANSITO:"bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400",
  ENTREGUE:   "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400",
};

const TRANSPORTADORAS = {
  "b32bd9f2-6122-4c84-b721-b284aec6072c": "Transportadora Expressa B2B",
  "fb22af19-4e13-4a1c-b1aa-e9e1e2dc7806": "Goyazes Express",
  "e7a28570-a7f2-44fa-8141-6ed3c22ef8c3": "Rápido Planalto",
  "09741881-8585-4ebd-bae0-58a637b8e647": "TransCerrado",
};

function formatCurrency(v) {
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function timeAgo(dateStr) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s atrás`;
  if (diff < 3600) return `${Math.floor(diff / 60)}min atrás`;
  return `${Math.floor(diff / 3600)}h atrás`;
}

export default function SolicitacaoCard({ solicitacao, onContratar }) {
  const s = solicitacao;
  const cotacoes = s.cotacoes || [];
  const freteId = s.frete_selecionado?.cotacao_id;

  const sorted = [...cotacoes].sort((a, b) => Number(a.valor) - Number(b.valor));
  const menorValorId = sorted[0]?.id ?? null;

  // Estado local de seleção manual (só ativo enquanto status === "COTADO")
  const [cotacaoEscolhidaId, setCotacaoEscolhidaId] = useState(null);
  const [contratando, setContratando] = useState(false);
  const [erroContrato, setErroContrato] = useState(null);

  const isCotado = s.status === "COTADO";
  const podeContratar = isCotado && cotacaoEscolhidaId !== null;

  async function handleContratar() {
    if (!podeContratar) return;
    setContratando(true);
    setErroContrato(null);
    try {
      await api.contratarFrete(s.id, cotacaoEscolhidaId);
      if (onContratar) onContratar(s.id);
    } catch (err) {
      setErroContrato(err.message || "Erro ao contratar. Tente novamente.");
    } finally {
      setContratando(false);
    }
  }

  return (
    <div className="card animate-fade-in flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col gap-2 border-b border-gray-100 pb-3 dark:border-slate-700/50">
        <div className="flex items-start justify-between gap-2">
          <div className="break-all">
            <p className="text-xs font-mono text-gray-500 dark:text-slate-400">
              <span className="font-semibold text-gray-700 dark:text-gray-300">Solicitação:</span> {s.id}
            </p>
            <p className="text-sm font-semibold text-gray-800 dark:text-gray-100 mt-1">
              Pedido ID: {s.pedido_id}
            </p>
          </div>
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${STATUS_COLORS[s.status] || "bg-gray-100 text-gray-500"}`}>
            {s.status?.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* Info chips */}
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-slate-700 dark:text-gray-300">
          🛣️ {s.tipo_transporte}
        </span>
        <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-slate-700 dark:text-gray-300">
          🕐 {timeAgo(s.data_criacao)}
        </span>
      </div>

      {/* Pipeline */}
      <div className="flex justify-center overflow-x-auto py-1">
        <StatusPipeline status={s.status} />
      </div>

      {/* ─── Cotações ─── */}
      {sorted.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-slate-500">
            {isCotado ? "Escolha uma Transportadora" : `Cotações (${sorted.length})`}
          </p>
          <div className="space-y-2">
            {sorted.map((c) => {
              const isSugestao = c.id === menorValorId;
              const isWinner   = c.id === freteId;
              const isSelected = isCotado && cotacaoEscolhidaId === c.id;
              const nome = TRANSPORTADORAS[c.transportadora_id] || "Transportadora Terceirizada";

              return (
                <div
                  key={c.id}
                  onClick={() => isCotado && setCotacaoEscolhidaId(c.id)}
                  className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-xs transition-all duration-200 ${
                    isCotado ? "cursor-pointer" : ""
                  } ${
                    isWinner
                      ? "border-2 border-brand-400 bg-brand-50 shadow-sm dark:border-brand-400/60 dark:bg-brand-400/10"
                      : isSelected
                      ? "border-2 border-orange-400 bg-orange-50 shadow-md dark:border-orange-400/60 dark:bg-orange-400/10"
                      : isCotado
                      ? "border border-gray-200 bg-gray-50 hover:border-orange-300 hover:bg-orange-50/50 dark:border-slate-700 dark:bg-slate-700/30 dark:hover:border-orange-500/50"
                      : "border border-gray-100 bg-gray-50 dark:border-slate-700/50 dark:bg-slate-700/30"
                  }`}
                >
                  {/* Radio button (apenas no modo COTADO) */}
                  {isCotado && (
                    <div className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-all ${
                      isSelected
                        ? "border-orange-500 bg-orange-500"
                        : "border-gray-300 dark:border-slate-600"
                    }`}>
                      {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                    </div>
                  )}

                  {/* Ícone vencedor (pós-contrato) */}
                  {!isCotado && isWinner && (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-400 text-[10px] text-white">
                      ★
                    </span>
                  )}

                  {/* Info transportadora */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className={`font-semibold break-words ${
                        isWinner ? "text-brand-700 dark:text-brand-300"
                        : isSelected ? "text-orange-700 dark:text-orange-300"
                        : "text-gray-800 dark:text-gray-200"
                      }`}>
                        {nome}
                      </p>
                      {/* Badge "Sugestão do Sistema" na menor cotação */}
                      {isSugestao && isCotado && (
                        <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[9px] font-bold text-orange-700 dark:bg-orange-500/20 dark:text-orange-400">
                          ⚡ Sugestão do Sistema
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-gray-500 dark:text-slate-400 mt-0.5">
                      Prazo: {c.prazo} dia{c.prazo > 1 ? "s" : ""} úteis
                    </p>
                  </div>

                  <span className={`font-bold text-right shrink-0 ${
                    isWinner ? "text-brand-600 dark:text-brand-400"
                    : isSelected ? "text-orange-600 dark:text-orange-400"
                    : "text-gray-600 dark:text-gray-400"
                  }`}>
                    {formatCurrency(c.valor)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── Botão "Finalizar Contrato" ── */}
          {isCotado && (
            <div className="mt-3 flex flex-col gap-2">
              <button
                onClick={handleContratar}
                disabled={!podeContratar || contratando}
                className={`w-full rounded-xl py-2.5 text-sm font-bold tracking-wide transition-all duration-200 ${
                  podeContratar && !contratando
                    ? "bg-orange-500 text-white shadow-md shadow-orange-500/30 hover:bg-orange-600 hover:shadow-lg active:scale-95"
                    : "cursor-not-allowed bg-gray-200 text-gray-400 dark:bg-slate-700 dark:text-slate-500"
                }`}
              >
                {contratando ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Contratando...
                  </span>
                ) : podeContratar ? (
                  "✅ Finalizar Contrato"
                ) : (
                  "Selecione uma transportadora para continuar"
                )}
              </button>
              {erroContrato && (
                <p className="text-center text-xs text-red-500 dark:text-red-400">{erroContrato}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Aguardando cotações */}
      {sorted.length === 0 && s.status === "AGUARDANDO" && (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 py-4 text-xs text-gray-400 dark:border-slate-700 dark:text-slate-500">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Gerando cotações...
        </div>
      )}
    </div>
  );
}
