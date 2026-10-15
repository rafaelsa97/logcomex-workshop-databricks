import { useEffect, useState } from "react";
import { api } from "./api.js";
import VisaoGeral from "./telas/VisaoGeral.jsx";
import Ncm from "./telas/Ncm.jsx";
import Rastreamento from "./telas/Rastreamento.jsx";
import Genie from "./telas/Genie.jsx";

const ABAS = [
  { id: "visao", rotulo: "Visão geral", icone: "📊", filtros: true },
  { id: "ncm", rotulo: "Inteligência de NCM", icone: "🔎", filtros: true },
  { id: "rastreio", rotulo: "Rastreamento", icone: "🚢" },
  { id: "genie", rotulo: "Pergunte ao Genie", icone: "✨" },
];
const ANOS = ["2026", "2025", "2024", "Todos"];
const VIAS = ["Marítima", "Aérea", "Rodoviária"];

export default function App() {
  const [aba, setAba] = useState("visao");
  const [filtros, setFiltros] = useState({ ano: "2026", vias: [] });
  const [config, setConfig] = useState({});
  useEffect(() => { api("config").then(setConfig).catch(() => {}); }, []);

  const alternarVia = (via) =>
    setFiltros((f) => ({ ...f, vias: f.vias.includes(via) ? f.vias.filter((v) => v !== via) : [...f.vias, via] }));
  const atual = ABAS.find((a) => a.id === aba);

  return (
    <div className="app">
      <header className="topo">
        <div className="topo-conteudo">
          <img src="./logo_branco.svg" alt="LogComex" className="logo" />
          <span className="produto">Radar Comex</span>
          <nav className="abas">
            {ABAS.map((a) => (
              <button key={a.id} className={a.id === aba ? "ativa" : ""} onClick={() => setAba(a.id)}>
                <span>{a.icone}</span> {a.rotulo}
              </button>
            ))}
          </nav>
          {config.dashboard_url && (
            <a className="link-dashboard" href={config.dashboard_url} target="_blank" rel="noreferrer">Dashboard AI/BI ↗</a>
          )}
        </div>
      </header>

      {atual.filtros && (
        <div className="barra-filtros">
          <div className="grupo">
            <span className="rotulo">Ano</span>
            <div className="segmentado">
              {ANOS.map((a) => (
                <button key={a} className={filtros.ano === a ? "ativo" : ""} onClick={() => setFiltros((f) => ({ ...f, ano: a }))}>{a}</button>
              ))}
            </div>
          </div>
          <div className="grupo">
            <span className="rotulo">Via de transporte</span>
            {VIAS.map((v) => (
              <button key={v} className={`chip ${filtros.vias.includes(v) ? "ativo" : ""}`} onClick={() => alternarVia(v)}>{v}</button>
            ))}
          </div>
        </div>
      )}

      <main className="conteudo">
        {aba === "visao" && <VisaoGeral filtros={filtros} />}
        {aba === "ncm" && <Ncm filtros={filtros} />}
        {aba === "rastreio" && <Rastreamento />}
        {aba === "genie" && <Genie habilitado={config.genie} />}
      </main>

      <footer className="rodape">
        React + FastAPI no <b>Databricks Apps</b> · dados {config.catalogo}.{config.schema} (sintéticos) · Unity Catalog + Databricks SQL + Genie
      </footer>
    </div>
  );
}
