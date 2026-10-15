"""Radar Comex — Databricks App do Workshop LogComex x Databricks.

Streamlit + Databricks SQL (tabelas Gold/Silver do Unity Catalog) + Genie Conversation API.
As credenciais vêm automaticamente do service principal do app (variáveis injetadas pelo Databricks Apps).
"""
import base64
import os
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

WAREHOUSE_ID = os.environ["WAREHOUSE_ID"]
CATALOGO = os.environ["CATALOGO"]
SCHEMA = os.environ["SCHEMA"]
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
T = f"`{CATALOGO}`.`{SCHEMA}`"

ROXO, ROXO_CLARO, PRETO, CANVAS = "#6613D0", "#B48BF0", "#0B0D19", "#F6F3FC"
PALETA = [ROXO, PRETO, ROXO_CLARO, "#3F3F46", "#9F67F5", "#A1A1AA", "#4A0E99", "#D8C7F7"]

st.set_page_config(page_title="Radar Comex · LogComex", page_icon="🟣", layout="wide")

# ------------------------------------------------------------------ identidade visual
logo = base64.b64encode((Path(__file__).parent / "logo_branco.svg").read_bytes()).decode()
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
  html, body, [class*="css"], .stMarkdown, .stTabs, button, input {{ font-family: 'Poppins', sans-serif; }}
  .block-container {{ padding-top: 1.2rem; }}
  .lc-header {{ background: {PRETO}; border-radius: 14px; padding: 18px 26px; display: flex; align-items: center;
               justify-content: space-between; border-bottom: 5px solid {ROXO}; margin-bottom: 18px; }}
  .lc-header img {{ height: 30px; }}
  .lc-header .tag {{ color: {ROXO_CLARO}; font-weight: 600; letter-spacing: .5px; }}
  .lc-kpi {{ background: white; border: 1px solid #ECE6F7; border-left: 6px solid {ROXO}; border-radius: 12px;
            padding: 14px 18px; }}
  .lc-kpi .rotulo {{ color: #5B5B6B; font-size: 13px; }}
  .lc-kpi .valor {{ color: {PRETO}; font-size: 26px; font-weight: 700; }}
  .stTabs [aria-selected="true"] {{ color: {ROXO} !important; }}
  div[data-testid="stSidebar"] {{ background: {CANVAS}; }}
</style>
<div class="lc-header">
  <img src="data:image/svg+xml;base64,{logo}" />
  <span class="tag">RADAR COMEX · powered by Databricks</span>
</div>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ acesso a dados
@st.cache_resource
def conexao():
    cfg = Config()  # usa o service principal do app
    return sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                       credentials_provider=lambda: cfg.authenticate)


@st.cache_data(ttl=600, show_spinner="Consultando o Databricks SQL...")
def consulta(query: str) -> pd.DataFrame:
    with conexao().cursor() as cur:
        cur.execute(query)
        return cur.fetchall_arrow().to_pandas()


def kpi(coluna, rotulo, valor):
    coluna.markdown(f'<div class="lc-kpi"><div class="rotulo">{rotulo}</div><div class="valor">{valor}</div></div>',
                    unsafe_allow_html=True)


def usd(v):
    v = float(v or 0)
    for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= limite:
            return f"US$ {v / limite:,.1f}{sufixo}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {v:,.0f}"


def estilo(fig):
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font_family="Poppins", margin=dict(t=40, l=10, r=10, b=10),
                      legend_title_text="", colorway=PALETA)
    return fig


# ------------------------------------------------------------------ filtros
with st.sidebar:
    st.markdown("### Filtros")
    ano = st.selectbox("Ano", ["Todos", 2026, 2025, 2024], index=1)
    via = st.multiselect("Via de transporte", ["Marítima", "Aérea", "Rodoviária"], default=[])
    st.markdown("---")
    if DASHBOARD_URL:
        st.markdown(f"📊 [Abrir o dashboard AI/BI]({DASHBOARD_URL})")
    st.caption(f"Dados: `{CATALOGO}.{SCHEMA}` (sintéticos)")

filtro = "1=1"
if ano != "Todos":
    filtro += f" AND year(mes) = {ano}"
if via:
    filtro += " AND via_transporte IN (" + ",".join(f"'{v}'" for v in via) + ")"

aba_visao, aba_ncm, aba_rastreio, aba_genie = st.tabs(
    ["📊 Visão geral", "🔎 Inteligência de NCM", "🚢 Rastreamento de contêineres", "🧞 Pergunte ao Genie"])

# ------------------------------------------------------------------ aba 1: visão geral
with aba_visao:
    totais = consulta(f"""
        SELECT SUM(IF(fluxo='Importação', valor_fob_usd, 0)) AS imp, SUM(IF(fluxo='Exportação', valor_fob_usd, 0)) AS exp,
               SUM(qtd_operacoes) AS ops, SUM(toneladas) AS ton
        FROM {T}.gold_comercio_exterior_mensal WHERE {filtro}""").iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "FOB importado", usd(totais.imp))
    kpi(c2, "FOB exportado", usd(totais.exp))
    kpi(c3, "Saldo da balança", usd(float(totais.exp or 0) - float(totais.imp or 0)))
    kpi(c4, "Operações (DI + DU-E)", f"{int(totais.ops or 0):,}".replace(",", "."))

    esq, dir_ = st.columns([3, 2])
    mensal = consulta(f"""SELECT mes, fluxo, SUM(valor_fob_usd) AS valor_fob_usd FROM {T}.gold_comercio_exterior_mensal
                          WHERE {filtro} GROUP BY ALL ORDER BY mes""")
    esq.plotly_chart(estilo(px.line(mensal, x="mes", y="valor_fob_usd", color="fluxo", markers=True,
                                    title="Evolução mensal do valor FOB (US$)",
                                    color_discrete_map={"Importação": ROXO, "Exportação": PRETO})), use_container_width=True)
    cats = consulta(f"""SELECT categoria_ncm, SUM(valor_fob_usd) AS valor_fob_usd FROM {T}.gold_comercio_exterior_mensal
                        WHERE {filtro} AND fluxo = 'Importação' GROUP BY ALL ORDER BY valor_fob_usd DESC LIMIT 10""")
    dir_.plotly_chart(estilo(px.bar(cats.sort_values("valor_fob_usd"), x="valor_fob_usd", y="categoria_ncm", orientation="h",
                                    title="Top categorias importadas (FOB US$)", color_discrete_sequence=[ROXO])),
                      use_container_width=True)

    # 🏁 EXERCÍCIO DO LAB 4 ──────────────────────────────────────────────────────────────
    # Descomente o bloco abaixo, salve o arquivo e faça o redeploy (célula do notebook 04).
    # Ele adiciona um ranking de países de destino das exportações.
    #
    # destinos = consulta(f"""SELECT pais_parceiro, SUM(valor_fob_usd) AS valor_fob_usd
    #                         FROM {T}.gold_comercio_exterior_mensal
    #                         WHERE {filtro} AND fluxo = 'Exportação' GROUP BY ALL ORDER BY valor_fob_usd DESC LIMIT 10""")
    # st.plotly_chart(estilo(px.bar(destinos, x="pais_parceiro", y="valor_fob_usd",
    #                               title="Top 10 destinos das exportações (FOB US$)",
    #                               color_discrete_sequence=[PRETO])), use_container_width=True)
    # ─────────────────────────────────────────────────────────────────────────────────────

# ------------------------------------------------------------------ aba 2: inteligência de NCM
with aba_ncm:
    ncms = consulta(f"SELECT codigo_ncm, descricao FROM {T}.silver_ncm WHERE fluxo_predominante = 'Importação' ORDER BY descricao")
    opcoes = {f"{r.codigo_ncm} · {r.descricao}": r.codigo_ncm for r in ncms.itertuples()}
    padrao = next((i for i, k in enumerate(opcoes) if k.startswith("8703.80.00")), 0)
    escolhido = opcoes[st.selectbox("Escolha uma NCM", list(opcoes), index=padrao)]
    f_ncm = filtro.replace("year(mes)", "year(mes_registro)")
    det = consulta(f"""SELECT mes_registro AS mes, pais_origem, razao_social_importador, uf_importador, valor_fob_usd,
                              peso_liquido_kg, preco_medio_usd_kg, via_transporte
                       FROM {T}.silver_importacoes WHERE ncm = '{escolhido}' AND {f_ncm}""")
    if det.empty:
        st.info("Sem DIs para esta NCM com os filtros escolhidos.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        kpi(c1, "FOB importado", usd(det.valor_fob_usd.astype(float).sum()))
        kpi(c2, "DIs registradas", f"{len(det):,}".replace(",", "."))
        kpi(c3, "Importadores", f"{det.razao_social_importador.nunique()}")
        kpi(c4, "Preço médio por kg", f"US$ {det.valor_fob_usd.astype(float).sum() / det.peso_liquido_kg.sum():.2f}".replace(".", ","))
        a, b = st.columns(2)
        evol = det.groupby("mes", as_index=False).valor_fob_usd.sum()
        a.plotly_chart(estilo(px.area(evol, x="mes", y="valor_fob_usd", title="FOB mensal (US$)",
                                      color_discrete_sequence=[ROXO])), use_container_width=True)
        paises = det.groupby("pais_origem", as_index=False).valor_fob_usd.sum()
        b.plotly_chart(estilo(px.pie(paises, names="pais_origem", values="valor_fob_usd", hole=.55,
                                     title="Participação por país de origem")), use_container_width=True)
        st.markdown("##### Principais importadores")
        top = (det.groupby(["razao_social_importador", "uf_importador"], as_index=False)
                  .agg(dis=("valor_fob_usd", "size"), valor_fob_usd=("valor_fob_usd", "sum"))
                  .sort_values("valor_fob_usd", ascending=False).head(15))
        st.dataframe(top, use_container_width=True, hide_index=True,
                     column_config={"valor_fob_usd": st.column_config.NumberColumn("FOB (US$)", format="$ %.0f"),
                                    "razao_social_importador": "Importador", "uf_importador": "UF", "dis": "DIs"})

# ------------------------------------------------------------------ aba 3: rastreamento
with aba_rastreio:
    resumo = consulta(f"""SELECT status_embarque, COUNT(*) AS conteineres FROM {T}.gold_embarques GROUP BY ALL""")
    cols = st.columns(len(resumo) or 1)
    for col, r in zip(cols, resumo.sort_values("conteineres", ascending=False).itertuples()):
        kpi(col, r.status_embarque, f"{r.conteineres:,}".replace(",", "."))
    atrasados = consulta(f"""SELECT container, armador, navio, porto_origem, porto_destino, consignatario, eta_prevista, atraso_dias
                             FROM {T}.gold_embarques WHERE status_embarque = 'Em trânsito - atrasado'
                             ORDER BY atraso_dias DESC LIMIT 200""")
    st.markdown("##### Contêineres em trânsito com atraso")
    st.dataframe(atrasados, use_container_width=True, hide_index=True, height=260)
    padrao_ct = atrasados.container.iloc[0] if not atrasados.empty else ""
    container = st.text_input("🔎 Rastrear contêiner", value=padrao_ct).strip().upper()
    if container:
        ev = consulta(f"""SELECT data_hora_evento, codigo_evento, descricao_evento, local_evento, navio, eta_prevista
                          FROM {T}.silver_eventos_embarque WHERE container = '{container.replace("'", "")}' ORDER BY data_hora_evento""")
        if ev.empty:
            st.warning("Contêiner não encontrado.")
        else:
            st.caption(f"Navio **{ev.navio.iloc[0]}** · ETA prevista {pd.to_datetime(ev.eta_prevista.iloc[0]):%d/%m/%Y}")
            for r in ev.itertuples():
                st.markdown(f"<div style='border-left:4px solid {ROXO};padding:4px 12px;margin:6px 0'>"
                            f"<b>{pd.to_datetime(r.data_hora_evento):%d/%m/%Y %H:%M}</b> · {r.codigo_evento} — "
                            f"{r.descricao_evento} <span style='color:#6B7280'>({r.local_evento})</span></div>",
                            unsafe_allow_html=True)


# ------------------------------------------------------------------ aba 4: Genie
def genie(pergunta: str, conversa: str | None):
    """Envia a pergunta ao Genie space e aguarda a resposta (Genie Conversation API)."""
    w = WorkspaceClient()
    base = f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
    if conversa:
        msg = w.api_client.do("POST", f"{base}/conversations/{conversa}/messages", body={"content": pergunta})
        msg_id = msg.get("id") or msg.get("message_id")
    else:
        r = w.api_client.do("POST", f"{base}/start-conversation", body={"content": pergunta})
        conversa, msg_id = r["conversation_id"], r["message_id"]
    for _ in range(90):
        msg = w.api_client.do("GET", f"{base}/conversations/{conversa}/messages/{msg_id}")
        if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"):
            break
        time.sleep(2)
    resposta = {"texto": [], "sql": None, "descricao": None, "dados": None, "erro": None}
    if msg.get("status") != "COMPLETED":
        resposta["erro"] = (msg.get("error") or {}).get("error") or f"Status: {msg.get('status')}"
    for anexo in msg.get("attachments") or []:
        if anexo.get("text"):
            resposta["texto"].append(anexo["text"].get("content", ""))
        if anexo.get("query"):
            resposta["sql"] = anexo["query"].get("query")
            resposta["descricao"] = anexo["query"].get("description")
            res = w.api_client.do("GET", f"{base}/conversations/{conversa}/messages/{msg_id}/attachments/"
                                         f"{anexo['attachment_id']}/query-result")
            st_resp = res.get("statement_response", {})
            colunas = [c["name"] for c in st_resp.get("manifest", {}).get("schema", {}).get("columns", [])]
            df = pd.DataFrame(st_resp.get("result", {}).get("data_array", []) or [], columns=colunas)
            for c in df.columns:
                convertido = pd.to_numeric(df[c], errors="coerce")
                if convertido.notna().all() and len(df):
                    df[c] = convertido
            resposta["dados"] = df
    return conversa, resposta


def mostrar(resposta):
    if resposta.get("erro"):
        st.error(resposta["erro"])
    if resposta.get("descricao"):
        st.markdown(resposta["descricao"])
    for t in resposta.get("texto", []):
        st.markdown(t)
    df = resposta.get("dados")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        numericas = df.select_dtypes("number").columns
        if 1 < len(df) <= 60 and len(df.columns) >= 2 and len(numericas) and df.columns[0] not in numericas:
            st.plotly_chart(estilo(px.bar(df, x=df.columns[0], y=numericas[0], color_discrete_sequence=[ROXO])),
                            use_container_width=True)
    if resposta.get("sql"):
        with st.expander("Ver SQL gerado pelo Genie"):
            st.code(resposta["sql"], language="sql")


with aba_genie:
    if not GENIE_SPACE_ID:
        st.info("Configure o GENIE_SPACE_ID (Lab 3) e faça o redeploy do app.")
    else:
        st.markdown("Pergunte em português sobre importações, exportações, desembaraço e rastreamento. "
                    "As respostas vêm do **Genie space** criado no Lab 3.")
        st.session_state.setdefault("historico", [])
        st.session_state.setdefault("conversa", None)
        sugestoes = ["Quais os 5 maiores importadores de veículos elétricos em 2026?",
                     "Qual armador tem o maior atraso médio nas rotas da Ásia?",
                     "Qual o saldo da balança comercial por trimestre em 2026?"]
        cols = st.columns(len(sugestoes))
        clicada = next((s for c, s in zip(cols, sugestoes) if c.button(s, use_container_width=True)), None)
        if st.button("🧹 Nova conversa"):
            st.session_state.historico, st.session_state.conversa = [], None
        for item in st.session_state.historico:
            with st.chat_message(item["papel"], avatar="🧑‍💼" if item["papel"] == "user" else "🟣"):
                mostrar(item["conteudo"]) if item["papel"] == "assistant" else st.markdown(item["conteudo"])
        pergunta = st.chat_input("Ex.: Como evoluiu a importação de painéis solares por trimestre?") or clicada
        if pergunta:
            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(pergunta)
            with st.chat_message("assistant", avatar="🟣"):
                with st.spinner("O Genie está analisando os dados..."):
                    try:
                        st.session_state.conversa, resposta = genie(pergunta, st.session_state.conversa)
                    except Exception as erro:  # noqa: BLE001 — mostrar o erro ao usuário do workshop
                        resposta = {"erro": f"Falha ao consultar o Genie: {erro}"}
                mostrar(resposta)
            st.session_state.historico += [{"papel": "user", "conteudo": pergunta},
                                           {"papel": "assistant", "conteudo": resposta}]
