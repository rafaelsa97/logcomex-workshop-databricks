import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, qs } from "../api.js";
import { Card, Estado, Kpi, useDados } from "../componentes.jsx";
import { PALETA, ROXO, curto, inteiro, mes, usd } from "../formato.js";

export default function Ncm({ filtros }) {
  const lista = useDados(() => api("ncms"), []);
  const [codigo, setCodigo] = useState("8703.80.00");
  const detalhe = useDados(() => api(`ncm/${encodeURIComponent(codigo)}?${qs(filtros)}`), [codigo, filtros]);

  return (
    <>
      <div className="seletor-ncm">
        <label>NCM</label>
        <select value={codigo} onChange={(e) => setCodigo(e.target.value)}>
          {(lista.dados || [{ codigo, descricao: "carregando..." }]).map((n) => (
            <option key={n.codigo} value={n.codigo}>{n.codigo} · {n.descricao}</option>
          ))}
        </select>
      </div>
      <Estado estado={detalhe}>
        {({ totais, mensal, paises, importadores }) =>
          !totais.dis ? (
            <div className="aviso">Sem DIs para esta NCM com os filtros escolhidos.</div>
          ) : (
            <>
              <div className="grade-kpis">
                <Kpi rotulo="FOB importado" valor={usd(totais.valor)} />
                <Kpi rotulo="DIs registradas" valor={inteiro(totais.dis)} />
                <Kpi rotulo="Importadores" valor={inteiro(totais.importadores)} />
                <Kpi rotulo="Preço médio por kg" valor={`US$ ${Number(totais.preco_kg || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} destaque />
              </div>
              <div className="grade-2">
                <Card titulo="FOB mensal" subtitulo="US$">
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={mensal} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="#EEE9F7" vertical={false} />
                      <XAxis dataKey="mes" tickFormatter={mes} tick={{ fontSize: 12 }} />
                      <YAxis tickFormatter={curto} tick={{ fontSize: 12 }} width={70} />
                      <Tooltip formatter={(v) => usd(v)} labelFormatter={mes} />
                      <Area type="monotone" dataKey="valor" name="FOB" stroke={ROXO} strokeWidth={2.5} fill={ROXO} fillOpacity={0.15} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>
                <Card titulo="Participação por país de origem">
                  <div className="pizza">
                    <ResponsiveContainer width="55%" height={280}>
                      <PieChart>
                        <Pie data={paises} dataKey="valor" nameKey="pais" innerRadius={70} outerRadius={115} paddingAngle={2}>
                          {paises.map((_, i) => <Cell key={i} fill={PALETA[i % PALETA.length]} />)}
                        </Pie>
                        <Tooltip formatter={(v) => usd(v)} />
                      </PieChart>
                    </ResponsiveContainer>
                    <ul className="legenda">
                      {paises.map((p, i) => (
                        <li key={p.pais}><i style={{ background: PALETA[i % PALETA.length] }} />{p.pais}<b>{usd(p.valor)}</b></li>
                      ))}
                    </ul>
                  </div>
                </Card>
              </div>
              <Card titulo="Principais importadores">
                <table className="tabela">
                  <thead><tr><th>#</th><th>Importador</th><th>UF</th><th className="num">DIs</th><th className="num">FOB (US$)</th><th style={{ width: "22%" }}>Participação</th></tr></thead>
                  <tbody>
                    {importadores.map((r, i) => (
                      <tr key={r.importador}>
                        <td className="posicao">{i + 1}</td><td>{r.importador}</td><td>{r.uf}</td>
                        <td className="num">{inteiro(r.dis)}</td><td className="num">{usd(r.valor)}</td>
                        <td><div className="barra"><span style={{ width: `${(100 * r.valor) / totais.valor}%` }} /></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </>
          )
        }
      </Estado>
    </>
  );
}
