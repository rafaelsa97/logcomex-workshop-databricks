import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, qs } from "../api.js";
import { Card, Estado, Kpi, useDados } from "../componentes.jsx";
import { PRETO, ROXO, curto, inteiro, mes, usd } from "../formato.js";

export default function VisaoGeral({ filtros }) {
  const estado = useDados(() => api(`visao-geral?${qs(filtros)}`), [filtros]);
  return (
    <Estado estado={estado}>
      {({ totais, mensal, categorias, destinos }) => {
        const saldo = Number(totais.exportado || 0) - Number(totais.importado || 0);
        return (
          <>
            <div className="grade-kpis">
              <Kpi rotulo="FOB importado" valor={usd(totais.importado)} />
              <Kpi rotulo="FOB exportado" valor={usd(totais.exportado)} />
              <Kpi rotulo="Saldo da balança" valor={usd(saldo)} destaque detalhe={saldo >= 0 ? "Superávit" : "Déficit"} />
              <Kpi rotulo="Operações (DI + DU-E)" valor={inteiro(totais.operacoes)} detalhe={`${curto(totais.toneladas)} de toneladas movimentadas`} />
            </div>
            <Card titulo="Evolução mensal do valor FOB" subtitulo="US$">
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={mensal} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gImp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={ROXO} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={ROXO} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#EEE9F7" vertical={false} />
                  <XAxis dataKey="mes" tickFormatter={mes} tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={curto} tick={{ fontSize: 12 }} width={70} />
                  <Tooltip formatter={(v) => usd(v)} labelFormatter={mes} />
                  <Legend />
                  <Area type="monotone" dataKey="importado" name="Importação" stroke={ROXO} strokeWidth={2.5} fill="url(#gImp)" />
                  <Area type="monotone" dataKey="exportado" name="Exportação" stroke={PRETO} strokeWidth={2.5} fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
            <div className="grade-2">
              <Card titulo="Top categorias importadas" subtitulo="FOB US$">
                <Barras dados={categorias} chave="categoria" cor={ROXO} />
              </Card>
              <Card titulo="Top destinos das exportações" subtitulo="FOB US$">
                <Barras dados={destinos} chave="pais" cor={PRETO} />
              </Card>
            </div>
          </>
        );
      }}
    </Estado>
  );
}

export function Barras({ dados, chave, cor, altura = 300 }) {
  return (
    <ResponsiveContainer width="100%" height={altura}>
      <BarChart data={dados} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
        <CartesianGrid stroke="#EEE9F7" horizontal={false} />
        <XAxis type="number" tickFormatter={curto} tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey={chave} width={170} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v) => usd(v)} cursor={{ fill: "#F6F3FC" }} />
        <Bar dataKey="valor" name="FOB" fill={cor} radius={[0, 6, 6, 0]} barSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}
