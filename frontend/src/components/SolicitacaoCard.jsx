import StatusPipeline from "./StatusPipeline.jsx";

const STATUS_COLORS = {
  AGUARDANDO: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
  SELECIONADO: "bg-brand-100 text-brand-700 dark:bg-brand-400/15 dark:text-brand-400",
  EM_TRANSITO: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400",
  ENTREGUE: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400",
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

export default function SolicitacaoCard({ solicitacao }) {
  const s = solicitacao;
  const cotacoes = s.cotacoes || [];
  const freteId = s.frete_selecionado?.cotacao_id;

  const sorted = [...cotacoes].sort((a, b) => Number(a.valor) - Number(b.valor));

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
            {s.status?.replace("_", " ")}
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

      {/* Cotações */}
      {sorted.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-slate-500">
            Cotações ({sorted.length})
          </p>
          <div className="space-y-1.5">
            {sorted.map((c, i) => {
              const isWinner = c.id === freteId;
              const nome = TRANSPORTADORAS[c.transportadora_id] || "Transportadora Terceirizada";

              return (
                <div
                  key={c.id}
                  className={`flex items-center justify-between rounded-xl px-3 py-2 text-xs transition-all ${
                    isWinner
                      ? "border-2 border-brand-400 bg-brand-50 shadow-sm dark:border-brand-400/60 dark:bg-brand-400/10"
                      : "border border-gray-100 bg-gray-50 dark:border-slate-700/50 dark:bg-slate-700/30"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {isWinner && (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-400 text-[10px] text-white">
                        ★
                      </span>
                    )}
                    <div>
                      <p className={`font-semibold break-words ${isWinner ? "text-brand-700 dark:text-brand-300" : "text-gray-800 dark:text-gray-200"}`}>
                        {nome}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-slate-400">
                        Prazo: {c.prazo} dia{c.prazo > 1 ? "s" : ""} úteis
                      </p>
                    </div>
                  </div>
                  <span className={`font-bold ${isWinner ? "text-brand-600 dark:text-brand-400" : "text-gray-600 dark:text-gray-400"}`}>
                    {formatCurrency(c.valor)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Loading cotações */}
      {sorted.length === 0 && s.status === "AGUARDANDO" && (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 py-4 text-xs text-gray-400 dark:border-slate-700 dark:text-slate-500">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Aguardando cotações...
        </div>
      )}
    </div>
  );
}
