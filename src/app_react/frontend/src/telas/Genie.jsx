import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { ROXO } from "../formato.js";

const SUGESTOES = [
  "Quais os 5 maiores importadores de veículos elétricos em 2026?",
  "Qual armador tem o maior atraso médio nas rotas da Ásia?",
  "Qual o saldo da balança comercial por trimestre em 2026?",
  "Como evoluiu o tempo de desembaraço em Paranaguá em 2026?",
];

// Markdown mínimo (negrito, itálico, listas e quebras de linha) com o texto escapado antes.
function markdown(texto) {
  const seguro = texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return seguro
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|\s)\*(.+?)\*/g, "$1<i>$2</i>")
    .replace(/^\s*[-*] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\s*)+/g, (m) => `<ul>${m.replace(/\s*\n\s*/g, "")}</ul>`)
    .replace(/\n/g, "<br/>");
}

const numero = (v) => v !== null && v !== "" && !isNaN(Number(v));
const formatar = (v) => (numero(v) ? Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : v);

export default function Genie({ habilitado }) {
  const [mensagens, setMensagens] = useState([]);
  const [conversa, setConversa] = useState(null);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const fim = useRef(null);
  useEffect(() => { fim.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens, pensando]);

  async function perguntar(pergunta) {
    if (!pergunta.trim() || pensando) return;
    setTexto("");
    setMensagens((m) => [...m, { papel: "usuario", pergunta }]);
    setPensando(true);
    try {
      const r = await api("genie", { method: "POST", body: JSON.stringify({ pergunta, conversa }) });
      setConversa(r.conversa);
      setMensagens((m) => [...m, { papel: "genie", ...r }]);
    } catch (erro) {
      setMensagens((m) => [...m, { papel: "genie", erro: `Falha ao consultar o Genie: ${erro.message}` }]);
    } finally {
      setPensando(false);
    }
  }

  if (habilitado === false) return <div className="aviso">Configure o Genie space (Lab 3) e publique o app novamente.</div>;

  return (
    <div className="genie">
      <div className="genie-topo">
        <div>
          <h2>Pergunte ao Genie</h2>
          <p>Perguntas em português sobre importações, exportações, desembaraço e rastreamento — respondidas pelo Genie space do Lab 3, com as permissões do Unity Catalog.</p>
        </div>
        {mensagens.length > 0 && <button className="secundario" onClick={() => { setMensagens([]); setConversa(null); }}>Nova conversa</button>}
      </div>

      {mensagens.length === 0 && (
        <div className="sugestoes">
          {SUGESTOES.map((s) => <button key={s} onClick={() => perguntar(s)}>{s}</button>)}
        </div>
      )}

      <div className="mensagens">
        {mensagens.map((m, i) => (m.papel === "usuario"
          ? <div key={i} className="balao usuario">{m.pergunta}</div>
          : <Resposta key={i} r={m} />))}
        {pensando && <div className="balao assistente pensando"><span /><span /><span /> O Genie está analisando os dados...</div>}
        <div ref={fim} />
      </div>

      <form className="entrada" onSubmit={(e) => { e.preventDefault(); perguntar(texto); }}>
        <input value={texto} onChange={(e) => setTexto(e.target.value)} disabled={pensando}
               placeholder="Ex.: Como evoluiu a importação de painéis solares por trimestre?" />
        <button disabled={pensando || !texto.trim()}>Enviar</button>
      </form>
    </div>
  );
}

function Resposta({ r }) {
  const linhas = r.linhas || [];
  const colunas = r.colunas || [];
  // Gráfico automático: 1ª coluna como rótulo e a métrica mais relevante (valor/FOB/total, senão a última numérica).
  const numericas = colunas.map((c, j) => j).filter((j) => j > 0 && linhas.length && linhas.every((l) => numero(l[j])));
  const indiceNumerico = numericas.find((j) => /valor|fob|total|saldo|media|medio|pct/i.test(colunas[j])) ?? numericas.at(-1) ?? -1;
  const grafico = linhas.length > 1 && linhas.length <= 25 && indiceNumerico > 0 && !numero(linhas[0][0]);
  const dados = grafico ? linhas.map((l) => ({ rotulo: String(l[0]), valor: Number(l[indiceNumerico]) })) : [];
  const abreviar = (s) => (s.length > 28 ? `${s.slice(0, 27)}…` : s);

  return (
    <div className="balao assistente">
      {r.erro && <div className="aviso aviso-erro">{r.erro}</div>}
      {r.descricao && <div className="descricao" dangerouslySetInnerHTML={{ __html: markdown(r.descricao) }} />}
      {(r.textos || []).map((t, i) => <div key={i} dangerouslySetInnerHTML={{ __html: markdown(t) }} />)}
      {grafico && (
        <ResponsiveContainer width="100%" height={Math.max(160, dados.length * 34 + 40)}>
          <BarChart data={dados} layout="vertical" margin={{ top: 12, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid stroke="#EEE9F7" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => Number(v).toLocaleString("pt-BR", { notation: "compact" })} />
            <YAxis type="category" dataKey="rotulo" width={210} tick={{ fontSize: 12 }} tickFormatter={abreviar} />
            <Tooltip formatter={(v) => formatar(v)} cursor={{ fill: "#F6F3FC" }} />
            <Bar dataKey="valor" name={colunas[indiceNumerico]} fill={ROXO} radius={[0, 6, 6, 0]} barSize={18} />
          </BarChart>
        </ResponsiveContainer>
      )}
      {linhas.length > 0 && (
        <div className="rolagem pequena">
          <table className="tabela">
            <thead><tr>{colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{linhas.slice(0, 50).map((l, i) => <tr key={i}>{l.map((v, j) => <td key={j} className={numero(v) ? "num" : ""}>{formatar(v)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
      {r.sql && (
        <details className="sql">
          <summary>Ver SQL gerado pelo Genie</summary>
          <pre>{r.sql}</pre>
        </details>
      )}
    </div>
  );
}
