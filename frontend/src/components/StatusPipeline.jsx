const STEPS = [
  { key: "AGUARDANDO", label: "Aguardando", icon: "⏳" },
  { key: "COTADO", label: "Cotado", icon: "📋" },
  { key: "SELECIONADO", label: "Selecionado", icon: "✅" },
  { key: "EM_TRANSITO", label: "Em Trânsito", icon: "🚚" },
  { key: "ENTREGUE", label: "Entregue", icon: "📦" },
];

function statusIndex(status) {
  if (status === "AGUARDANDO") return 0;
  if (status === "SELECIONADO") return 2;
  if (status === "EM_TRANSITO") return 3;
  if (status === "ENTREGUE") return 4;
  return 0;
}

export default function StatusPipeline({ status }) {
  const current = statusIndex(status);

  return (
    <div className="flex items-center gap-0.5">
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current;
        const future = i > current;

        return (
          <div key={step.key} className="flex items-center">
            {/* Node */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all duration-500 ${
                  done
                    ? "bg-brand-400 text-white shadow-md shadow-brand-400/30"
                    : active
                    ? "bg-brand-400 text-white shadow-lg shadow-brand-400/40 ring-4 ring-brand-400/20 scale-110"
                    : "bg-gray-200 text-gray-400 dark:bg-slate-700 dark:text-slate-500"
                } ${active && status === "EM_TRANSITO" ? "animate-bounce-truck" : ""}`}
              >
                {done ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <span className="text-sm">{step.icon}</span>
                )}
              </div>
              <span
                className={`mt-1 text-[9px] font-semibold uppercase tracking-wide ${
                  done || active ? "text-brand-500 dark:text-brand-400" : "text-gray-400 dark:text-slate-600"
                }`}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div
                className={`mb-4 h-0.5 w-4 transition-all duration-500 sm:w-6 ${
                  i < current ? "bg-brand-400" : "bg-gray-200 dark:bg-slate-700"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
