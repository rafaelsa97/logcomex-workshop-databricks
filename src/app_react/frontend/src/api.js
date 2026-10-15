// Cliente da API FastAPI (mesma origem: o app é servido pelo próprio backend).
export async function api(caminho, opcoes = {}) {
  const resp = await fetch(`./api/${caminho}`, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    throw new Error(corpo.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

export const qs = (filtros) => `ano=${filtros.ano}&vias=${encodeURIComponent(filtros.vias.join(","))}`;
