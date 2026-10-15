"""Radar Comex (React) — versão "produto" do app do Workshop LogComex x Databricks.

FastAPI serve a API (/api/*) e o frontend React já compilado (pasta static/).
Mesmas fontes do app Streamlit: tabelas Gold/Silver via Databricks SQL + Genie Conversation API,
com a identidade do service principal do app.
"""
import os
import time
from pathlib import Path

from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

WAREHOUSE_ID = os.environ["WAREHOUSE_ID"]
CATALOGO = os.environ["CATALOGO"]
SCHEMA = os.environ["SCHEMA"]
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
T = f"`{CATALOGO}`.`{SCHEMA}`"
VIAS = ("Marítima", "Aérea", "Rodoviária")

cfg = Config()  # service principal do app (ou perfil local em desenvolvimento)
w = WorkspaceClient(config=cfg)
app = FastAPI(title="Radar Comex API")


# ------------------------------------------------------------------ acesso a dados
_conexao = None
_cache: dict = {}


def consulta(query: str, params: dict | None = None, ttl: int = 600) -> list[dict]:
    """Executa SQL parametrizado no warehouse e devolve linhas como dicionários (com cache simples)."""
    global _conexao
    chave = (query, tuple(sorted((params or {}).items())))
    if chave in _cache and time.time() - _cache[chave][0] < ttl:
        return _cache[chave][1]
    for tentativa in range(2):
        try:
            if _conexao is None:
                _conexao = sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                                       credentials_provider=lambda: cfg.authenticate)
            with _conexao.cursor() as cur:
                cur.execute(query, params or {})
                colunas = [c[0] for c in cur.description]
                linhas = [dict(zip(colunas, r)) for r in cur.fetchall()]
            break
        except Exception:
            _conexao = None  # conexão expirada: reconecta uma vez
            if tentativa:
                raise
    _cache[chave] = (time.time(), linhas)
    return linhas


def filtros(ano: str, vias: str, coluna_mes: str = "mes") -> tuple[str, dict]:
    """Monta o WHERE dos filtros globais (ano e vias de transporte) com parâmetros nomeados."""
    clausula, params = "1=1", {}
    if ano and ano != "Todos":
        clausula += f" AND year({coluna_mes}) = :ano"
        params["ano"] = int(ano)
    escolhidas = [v for v in (vias or "").split(",") if v in VIAS]
    if escolhidas:
        clausula += " AND via_transporte IN (" + ",".join(f":via{i}" for i in range(len(escolhidas))) + ")"
        params |= {f"via{i}": v for i, v in enumerate(escolhidas)}
    return clausula, params


# ------------------------------------------------------------------ API
@app.get("/api/config")
def config():
    return {"catalogo": CATALOGO, "schema": SCHEMA, "dashboard_url": DASHBOARD_URL, "genie": bool(GENIE_SPACE_ID)}


@app.get("/api/visao-geral")
def visao_geral(ano: str = "2026", vias: str = ""):
    f, p = filtros(ano, vias)
    totais = consulta(f"""
        SELECT SUM(IF(fluxo = 'Importação', valor_fob_usd, 0)) AS importado, SUM(IF(fluxo = 'Exportação', valor_fob_usd, 0)) AS exportado,
               SUM(qtd_operacoes) AS operacoes, SUM(toneladas) AS toneladas
        FROM {T}.gold_comercio_exterior_mensal WHERE {f}""", p)[0]
    mensal = consulta(f"""
        SELECT date_format(mes, 'yyyy-MM') AS mes, SUM(IF(fluxo = 'Importação', valor_fob_usd, 0)) AS importado,
               SUM(IF(fluxo = 'Exportação', valor_fob_usd, 0)) AS exportado
        FROM {T}.gold_comercio_exterior_mensal WHERE {f} GROUP BY 1 ORDER BY 1""", p)
    categorias = consulta(f"""
        SELECT categoria_ncm AS categoria, SUM(valor_fob_usd) AS valor FROM {T}.gold_comercio_exterior_mensal
        WHERE {f} AND fluxo = 'Importação' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""", p)
    destinos = consulta(f"""
        SELECT pais_parceiro AS pais, SUM(valor_fob_usd) AS valor FROM {T}.gold_comercio_exterior_mensal
        WHERE {f} AND fluxo = 'Exportação' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""", p)
    return {"totais": totais, "mensal": mensal, "categorias": categorias, "destinos": destinos}


@app.get("/api/ncms")
def ncms():
    return consulta(f"""SELECT codigo_ncm AS codigo, descricao FROM {T}.silver_ncm
                        WHERE fluxo_predominante = 'Importação' ORDER BY descricao""")


@app.get("/api/ncm/{codigo}")
def ncm(codigo: str, ano: str = "2026", vias: str = ""):
    f, p = filtros(ano, vias, "mes_registro")
    p["ncm"] = codigo
    base = f"FROM {T}.silver_importacoes WHERE ncm = :ncm AND {f}"
    totais = consulta(f"""SELECT SUM(valor_fob_usd) AS valor, COUNT(*) AS dis, COUNT(DISTINCT cnpj_importador) AS importadores,
                                 SUM(valor_fob_usd) / NULLIF(SUM(peso_liquido_kg), 0) AS preco_kg {base}""", p)[0]
    mensal = consulta(f"SELECT date_format(mes_registro, 'yyyy-MM') AS mes, SUM(valor_fob_usd) AS valor {base} GROUP BY 1 ORDER BY 1", p)
    paises = consulta(f"SELECT pais_origem AS pais, SUM(valor_fob_usd) AS valor {base} GROUP BY 1 ORDER BY 2 DESC LIMIT 6", p)
    importadores = consulta(f"""SELECT razao_social_importador AS importador, uf_importador AS uf, COUNT(*) AS dis,
                                       SUM(valor_fob_usd) AS valor {base} GROUP BY 1, 2 ORDER BY 4 DESC LIMIT 10""", p)
    return {"totais": totais, "mensal": mensal, "paises": paises, "importadores": importadores}


@app.get("/api/rastreamento")
def rastreamento():
    status = consulta(f"SELECT status_embarque AS status, COUNT(*) AS conteineres FROM {T}.gold_embarques GROUP BY 1 ORDER BY 2 DESC")
    atrasados = consulta(f"""SELECT container, armador, navio, porto_origem, porto_destino, consignatario,
                                    date_format(eta_prevista, 'dd/MM/yyyy') AS eta, atraso_dias
                             FROM {T}.gold_embarques WHERE status_embarque = 'Em trânsito - atrasado'
                             ORDER BY atraso_dias DESC LIMIT 100""")
    return {"status": status, "atrasados": atrasados}


@app.get("/api/conteiner/{container}")
def conteiner(container: str):
    eventos = consulta(f"""SELECT date_format(data_hora_evento, 'dd/MM/yyyy HH:mm') AS quando, codigo_evento AS codigo,
                                  descricao_evento AS descricao, local_evento AS local, navio,
                                  date_format(eta_prevista, 'dd/MM/yyyy') AS eta
                           FROM {T}.silver_eventos_embarque WHERE container = :c ORDER BY data_hora_evento""",
                       {"c": container.strip().upper()}, ttl=60)
    if not eventos:
        raise HTTPException(404, "Contêiner não encontrado.")
    return eventos


class Pergunta(BaseModel):
    pergunta: str
    conversa: str | None = None


@app.post("/api/genie")
def genie(entrada: Pergunta):
    """Envia a pergunta ao Genie space (Genie Conversation API) e devolve texto, SQL e dados."""
    if not GENIE_SPACE_ID:
        raise HTTPException(400, "Genie space não configurado — rode o Lab 3 e o notebook do app novamente.")
    base = f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
    if entrada.conversa:
        msg = w.api_client.do("POST", f"{base}/conversations/{entrada.conversa}/messages", body={"content": entrada.pergunta})
        conversa, msg_id = entrada.conversa, msg.get("id") or msg.get("message_id")
    else:
        r = w.api_client.do("POST", f"{base}/start-conversation", body={"content": entrada.pergunta})
        conversa, msg_id = r["conversation_id"], r["message_id"]
    for _ in range(90):
        msg = w.api_client.do("GET", f"{base}/conversations/{conversa}/messages/{msg_id}")
        if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"):
            break
        time.sleep(2)
    resposta = {"conversa": conversa, "textos": [], "sql": None, "descricao": None, "colunas": [], "linhas": [], "erro": None}
    if msg.get("status") != "COMPLETED":
        resposta["erro"] = (msg.get("error") or {}).get("error") or f"Status: {msg.get('status')}"
    for anexo in msg.get("attachments") or []:
        if anexo.get("text"):
            resposta["textos"].append(anexo["text"].get("content", ""))
        if anexo.get("query"):
            resposta["sql"] = anexo["query"].get("query")
            resposta["descricao"] = anexo["query"].get("description")
            res = w.api_client.do("GET", f"{base}/conversations/{conversa}/messages/{msg_id}/attachments/"
                                         f"{anexo['attachment_id']}/query-result")
            st_resp = res.get("statement_response", {})
            resposta["colunas"] = [c["name"] for c in st_resp.get("manifest", {}).get("schema", {}).get("columns", [])]
            resposta["linhas"] = st_resp.get("result", {}).get("data_array", []) or []
    return resposta


# ------------------------------------------------------------------ frontend React (compilado em static/)
ESTATICOS = Path(__file__).parent / "static"
if (ESTATICOS / "assets").exists():
    app.mount("/assets", StaticFiles(directory=ESTATICOS / "assets"), name="assets")


@app.get("/{caminho:path}")
def spa(caminho: str):
    arquivo = ESTATICOS / caminho
    if caminho and arquivo.is_file() and ESTATICOS in arquivo.resolve().parents:
        return FileResponse(arquivo)
    return FileResponse(ESTATICOS / "index.html")
