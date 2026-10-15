export const ROXO = "#6613D0";
export const ROXO_ESCURO = "#4A0E99";
export const ROXO_CLARO = "#B48BF0";
export const PRETO = "#0B0D19";
export const PALETA = [ROXO, PRETO, ROXO_CLARO, "#3F3F46", "#9F67F5", "#A1A1AA", ROXO_ESCURO, "#D8C7F7"];

const num = (v, casas = 1) =>
  Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

// US$ 4,7 bi · US$ 578,0 mi · US$ 12,3 mil
export function usd(v) {
  const x = Number(v || 0);
  for (const [limite, sufixo] of [[1e9, " bi"], [1e6, " mi"], [1e3, " mil"]]) {
    if (Math.abs(x) >= limite) return `US$ ${num(x / limite)}${sufixo}`;
  }
  return `US$ ${num(x, 0)}`;
}

// Eixos dos gráficos: 4,7 bi
export const curto = (v) => usd(v).replace("US$ ", "");
export const inteiro = (v) => Number(v || 0).toLocaleString("pt-BR");
export const mes = (aaaamm) => {
  const [a, m] = String(aaaamm).split("-");
  return `${["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][Number(m) - 1]}/${a.slice(2)}`;
};
