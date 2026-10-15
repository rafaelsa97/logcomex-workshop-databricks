import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, Estado, Kpi, useDados } from "../componentes.jsx";
import { inteiro } from "../formato.js";

export default function Rastreamento() {
  const estado = useDados(() => api("rastreamento"), []);
  const [busca, setBusca] = useState("");
  const [selecionado, setSelecionado] = useState(null);
  useEffect(() => {
    const primeiro = estado.dados?.atrasados?.[0]?.container;
    if (primeiro && !selecionado) { setSelecionado(primeiro); setBusca(primeiro); }
  }, [estado.dados]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Estado estado={estado}>
      {({ status, atrasados }) => (
        <>
          <div className="grade-kpis" style={{ gridTemplateColumns: `repeat(${Math.min(status.length, 4)}, 1fr)` }}>
            {status.slice(0, 4).map((s) => (
              <Kpi key={s.status} rotulo={s.status} valor={inteiro(s.conteineres)} destaque={s.status.includes("atrasado")} />
            ))}
          </div>
          <div className="grade-rastreio">
            <Card titulo="Contêineres em trânsito com atraso" subtitulo={`${atrasados.length} contêineres · ordenados pelo atraso`}>
              <div className="rolagem">
                <table className="tabela clicavel">
                  <thead><tr><th>Contêiner</th><th>Armador</th><th>Rota</th><th>Consignatário</th><th>ETA</th><th className="num">Atraso</th></tr></thead>
                  <tbody>
                    {atrasados.map((r) => (
                      <tr key={r.container} className={r.container === selecionado ? "selecionada" : ""}
                          onClick={() => { setSelecionado(r.container); setBusca(r.container); }}>
                        <td className="mono">{r.container}</td><td>{r.armador}</td>
                        <td>{r.porto_origem} → {r.porto_destino.replace(/^Porto d[eo] /, "")}</td><td className="truncar">{r.consignatario}</td>
                        <td>{r.eta}</td><td className="num"><span className="pilula">+{Number(r.atraso_dias).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} d</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card titulo="Rastrear contêiner">
              <form className="busca" onSubmit={(e) => { e.preventDefault(); setSelecionado(busca.trim().toUpperCase()); }}>
                <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Ex.: MSCU1234567" />
                <button>Rastrear</button>
              </form>
              {selecionado && <LinhaDoTempo container={selecionado} />}
            </Card>
          </div>
        </>
      )}
    </Estado>
  );
}

function LinhaDoTempo({ container }) {
  const estado = useDados(() => api(`conteiner/${encodeURIComponent(container)}`), [container]);
  if (estado.carregando) return <div className="bloco" style={{ height: 200, marginTop: 12 }} />;
  if (estado.erro) return <div className="aviso">{estado.erro}</div>;
  const eventos = estado.dados;
  return (
    <>
      <div className="resumo-navio">🚢 <b>{eventos[0].navio}</b> · ETA prevista {eventos[0].eta}</div>
      <div className="rolagem-tempo"><ol className="linha-tempo">
        {eventos.map((e, i) => (
          <li key={i} className={i === eventos.length - 1 ? "ultimo" : ""}>
            <div className="quando">{e.quando}</div>
            <div><b>{e.codigo}</b> — {e.descricao}</div>
            <div className="local">{e.local}</div>
          </li>
        ))}
      </ol></div>
    </>
  );
}
