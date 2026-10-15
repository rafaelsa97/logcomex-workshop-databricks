import { useEffect, useState } from "react";

export function useDados(carregar, deps) {
  const [estado, setEstado] = useState({ dados: null, erro: null, carregando: true });
  useEffect(() => {
    let ativo = true;
    setEstado((e) => ({ ...e, carregando: true, erro: null }));
    carregar()
      .then((dados) => ativo && setEstado({ dados, erro: null, carregando: false }))
      .catch((erro) => ativo && setEstado({ dados: null, erro: erro.message, carregando: false }));
    return () => { ativo = false; };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return estado;
}

export function Kpi({ rotulo, valor, detalhe, destaque }) {
  return (
    <div className={`kpi ${destaque ? "kpi-destaque" : ""}`}>
      <div className="kpi-rotulo">{rotulo}</div>
      <div className="kpi-valor">{valor}</div>
      {detalhe && <div className="kpi-detalhe">{detalhe}</div>}
    </div>
  );
}

export function Card({ titulo, subtitulo, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {titulo && (
        <header className="card-cabecalho">
          <h3>{titulo}</h3>
          {subtitulo && <span>{subtitulo}</span>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Estado({ estado, children }) {
  if (estado.erro) return <div className="aviso aviso-erro">⚠️ {estado.erro}</div>;
  if (!estado.dados) return <Esqueleto />;
  return <div className={estado.carregando ? "recarregando" : ""}>{children(estado.dados)}</div>;
}

export function Esqueleto() {
  return (
    <div className="esqueleto">
      <div className="grade-kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="bloco" style={{ height: 96 }} />)}</div>
      <div className="bloco" style={{ height: 320, marginTop: 18 }} />
    </div>
  );
}
