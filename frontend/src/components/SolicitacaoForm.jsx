import { useState, useMemo } from "react";

const VEICULOS_MAP = {
  FURGAO: { label: "Furgão", icon: "🚐", faixa: "R$ 350–900" },
  CAMINHAO_3_4: { label: "Caminhão ¾", icon: "🚛", faixa: "R$ 800–1.800" },
  CAMINHAO_BAU_NORMAL: { label: "Baú Normal", icon: "📦", faixa: "R$ 1.500–3.500" },
  CAMINHAO_BAU_FRIGORIFICO: { label: "Frigorífico", icon: "🧊", faixa: "R$ 2.200–4.500" },
  CAMINHAO_SIDER: { label: "Sider", icon: "🚚", faixa: "R$ 1.800–3.800" },
};

function calcVeiculo(peso, natureza) {
  if (!peso || peso <= 0) return null;
  if (peso <= 1500) return "FURGAO";
  if (peso <= 4000) return "CAMINHAO_3_4";
  const n = (natureza || "SECA_GERAL").toUpperCase();
  if (n === "PERECIVEL") return "CAMINHAO_BAU_FRIGORIFICO";
  if (n === "CARGA_LATERAL") return "CAMINHAO_SIDER";
  return "CAMINHAO_BAU_NORMAL";
}

export default function SolicitacaoForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    tipo_transporte: "RODOVIARIO",
    peso_carga: "",
    tipo_carga_natureza: "",
    tipo_carga: "",
    cep_origem: "",
    cep_destino: "",
  });

  const veiculo = useMemo(
    () => calcVeiculo(Number(form.peso_carga), form.tipo_carga_natureza),
    [form.peso_carga, form.tipo_carga_natureza]
  );

  const veiculoInfo = veiculo ? VEICULOS_MAP[veiculo] : null;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    const dados = {
      pedido_id: crypto.randomUUID(),
      tipo_transporte: form.tipo_transporte,
    };
    if (form.peso_carga) dados.peso_carga = Number(form.peso_carga);
    if (form.tipo_carga_natureza) dados.tipo_carga_natureza = form.tipo_carga_natureza;
    if (form.tipo_carga) dados.tipo_carga = form.tipo_carga;
    if (form.cep_origem) dados.cep_origem = form.cep_origem;
    if (form.cep_destino) dados.cep_destino = form.cep_destino;
    onSubmit(dados);
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3 className="mb-4 flex items-center gap-2 text-base font-bold text-gray-800 dark:text-white">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-brand-400" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clipRule="evenodd" />
        </svg>
        Nova Solicitação de Frete
      </h3>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Tipo transporte */}
        <div>
          <label className="label">Tipo de Transporte</label>
          <select className="select-field" value={form.tipo_transporte} onChange={set("tipo_transporte")}>
            <option value="RODOVIARIO">🛣️ Rodoviário</option>
            <option value="AEREO">✈️ Aéreo</option>
            <option value="MARITIMO">🚢 Marítimo</option>
          </select>
        </div>

        {/* Peso */}
        <div>
          <label className="label">Peso da Carga (kg)</label>
          <input
            type="number"
            className="input-field"
            placeholder="Ex: 2500"
            min="0"
            step="0.01"
            value={form.peso_carga}
            onChange={set("peso_carga")}
          />
        </div>

        {/* Natureza */}
        <div>
          <label className="label">Natureza da Carga</label>
          <select className="select-field" value={form.tipo_carga_natureza} onChange={set("tipo_carga_natureza")}>
            <option value="">Selecionar...</option>
            <option value="SECA_GERAL">📦 Seca Geral</option>
            <option value="PERECIVEL">🧊 Perecível</option>
            <option value="CARGA_LATERAL">🔄 Carga Lateral</option>
          </select>
        </div>

        {/* Tipo carga */}
        <div>
          <label className="label">Tipo de Carga</label>
          <select className="select-field" value={form.tipo_carga} onChange={set("tipo_carga")}>
            <option value="">Selecionar...</option>
            <option value="GRANEL">Granel</option>
            <option value="FRACIONADA">Fracionada</option>
            <option value="CONTAINER">Container</option>
          </select>
        </div>

        {/* CEPs */}
        <div>
          <label className="label">CEP Origem</label>
          <input className="input-field" placeholder="Ex: 74000000" maxLength={8} value={form.cep_origem} onChange={set("cep_origem")} />
        </div>
        <div>
          <label className="label">CEP Destino</label>
          <input className="input-field" placeholder="Ex: 01001000" maxLength={8} value={form.cep_destino} onChange={set("cep_destino")} />
        </div>
      </div>

      {/* Vehicle preview */}
      {veiculoInfo && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-brand-400/30 bg-brand-50 px-4 py-3 dark:border-brand-400/20 dark:bg-brand-400/10">
          <span className="text-2xl">{veiculoInfo.icon}</span>
          <div>
            <p className="text-sm font-semibold text-brand-700 dark:text-brand-300">
              Veículo selecionado: {veiculoInfo.label}
            </p>
            <p className="text-xs text-brand-600/70 dark:text-brand-400/70">
              Faixa estimada: {veiculoInfo.faixa} • Código: {veiculo}
            </p>
          </div>
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Enviando...
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z" clipRule="evenodd" />
              </svg>
              Disparar Demo Completo
            </>
          )}
        </button>
      </div>
    </form>
  );
}
