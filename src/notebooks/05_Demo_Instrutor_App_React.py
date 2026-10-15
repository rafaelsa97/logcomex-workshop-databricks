# Databricks notebook source
# MAGIC %md
# MAGIC # 🎓 Demo do instrutor — o mesmo Radar Comex, agora como produto (React + FastAPI)
# MAGIC
# MAGIC **Opcional · só o instrutor roda · ~5 min** (use no fechamento do Lab 4).
# MAGIC
# MAGIC No Lab 4 publicamos o Radar Comex em **Streamlit**: ótimo para o time de dados prototipar em Python.
# MAGIC Este notebook publica **o mesmo app** reescrito como um produto web: frontend **React** (já compilado) +
# MAGIC API **FastAPI**, com as mesmas fontes de dados e a mesma governança.
# MAGIC
# MAGIC ```
# MAGIC  Navegador ──SSO──▶ Databricks App ┬─ React (HTML/JS estático, compilado com Vite)
# MAGIC                                    └─ FastAPI /api/* ──▶ SQL Warehouse ──▶ Gold/Silver (Unity Catalog)
# MAGIC                                                     └──▶ Genie Conversation API (espaço do Lab 3)
# MAGIC ```
# MAGIC
# MAGIC | | Streamlit (Lab 4) | React + FastAPI (esta demo) |
# MAGIC |---|---|---|
# MAGIC | Quem constrói | Time de dados, 100% Python | Time de produto/front-end |
# MAGIC | Interação | Script reexecutado a cada clique | Página única; só os dados trafegam |
# MAGIC | Uso típico | Protótipos, ferramentas internas | Produtos para clientes, white-label, API reutilizável |
# MAGIC | No Databricks | Mesmo SSO, mesmo service principal, mesmas permissões do Unity Catalog | ← idem |
# MAGIC
# MAGIC **Pré-requisito:** Labs 1–3 concluídos por este usuário (tabelas Gold, dashboard e Genie space).

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

import base64
import io
import zipfile

PACOTE_B64 = "__APP_REACT_ZIP_B64__"  # backend (app.py) + frontend React compilado (static/)

APP_REACT = re.sub(r"-+", "-", f"radar-react-{SLUG.replace('_', '-')}")[:30].strip("-")
PASTA_APP_REACT = f"{PASTA_USUARIO}/app_radar_comex_react"

WAREHOUSE_ID = escolher_warehouse()
GENIE_SPACE_ID = cfg_get("genie_space_id", "")
DASHBOARD_ID = cfg_get("dashboard_id", "")
DASHBOARD_URL = url_workspace(f"/dashboardsv3/{DASHBOARD_ID}/published") if DASHBOARD_ID else ""
assert spark.catalog.tableExists(f"{CATALOGO}.{SCHEMA}.gold_embarques"), "⚠️ Tabelas Gold não encontradas — rode os Labs 1–3 antes."

# 1) Extrai o código na pasta do usuário
w.workspace.mkdirs(PASTA_APP_REACT)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PACOTE_B64))) as pacote:
    for nome in pacote.namelist():
        if nome.endswith("/"):
            continue
        destino = f"{PASTA_APP_REACT}/{nome}"
        w.workspace.mkdirs(os.path.dirname(destino))
        with open(destino, "wb") as f:
            f.write(pacote.read(nome))
        print("📝", nome)

with open(f"{PASTA_APP_REACT}/app.yaml", "w") as f:
    f.write(f"""command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
env:
  - name: WAREHOUSE_ID
    value: "{WAREHOUSE_ID}"
  - name: CATALOGO
    value: "{CATALOGO}"
  - name: SCHEMA
    value: "{SCHEMA}"
  - name: GENIE_SPACE_ID
    value: "{GENIE_SPACE_ID}"
  - name: DASHBOARD_URL
    value: "{DASHBOARD_URL}"
""")
print(f"✅ Código gravado em {PASTA_APP_REACT}")

# COMMAND ----------

# 2) Cria o app e dá ao service principal as mesmas permissões mínimas do Lab 4
try:
    app = api("GET", f"/api/2.0/apps/{APP_REACT}")
except Exception:
    app = api("POST", "/api/2.0/apps", {"name": APP_REACT, "description": "Radar Comex (React + FastAPI) — demo do instrutor"})
SP = app["service_principal_client_id"]

for comando in [f"GRANT USE CATALOG ON CATALOG `{CATALOGO}` TO `{SP}`", f"GRANT USE SCHEMA, SELECT ON SCHEMA {FQ} TO `{SP}`"]:
    try:
        spark.sql(comando)
        print("✅", comando)
    except Exception as erro:
        print(f"⚠️ {comando}: {str(erro).splitlines()[0][:140]}")
for recurso, nivel in [(f"sql/warehouses/{WAREHOUSE_ID}", "CAN_USE"), (f"genie/{GENIE_SPACE_ID}", "CAN_RUN")]:
    if recurso.endswith("/"):
        continue
    try:
        api("PATCH", f"/api/2.0/permissions/{recurso}",
            {"access_control_list": [{"service_principal_name": SP, "permission_level": nivel}]})
        print(f"✅ {nivel} em {recurso}")
    except Exception as erro:
        print(f"⚠️ {recurso}: {str(erro).splitlines()[0][:140]}")

# COMMAND ----------

# 3) Deploy (o compute de um app novo leva alguns minutos para ficar ativo)
inicio = time.time()
while (estado := api("GET", f"/api/2.0/apps/{APP_REACT}").get("compute_status", {}).get("state")) != "ACTIVE":
    if estado in ("STOPPED", "ERROR"):
        api("POST", f"/api/2.0/apps/{APP_REACT}/start")
    if time.time() - inicio > 900:
        raise TimeoutError("O compute do app não ficou ativo a tempo — rode esta célula novamente.")
    print(f"⏳ compute do app: {estado}...")
    time.sleep(15)

dep = api("POST", f"/api/2.0/apps/{APP_REACT}/deployments", {"source_code_path": PASTA_APP_REACT, "mode": "SNAPSHOT"})
while (estado := api("GET", f"/api/2.0/apps/{APP_REACT}/deployments/{dep['deployment_id']}").get("status", {}).get("state")) in ("IN_PROGRESS", "PENDING"):
    print(f"⏳ deploy: {estado}...")
    time.sleep(10)

app = api("GET", f"/api/2.0/apps/{APP_REACT}")
if estado != "SUCCEEDED":
    raise RuntimeError(f"Deploy falhou ({estado}) — veja os logs em {app.get('url')}/logz")
cfg_set("app_react_url", app["url"])
displayHTML(f"""<div style="font-family:Poppins,Arial;background:{PRETO};color:white;padding:18px 24px;border-radius:12px;border-left:8px solid {ROXO}">
<div style="font-size:20px;font-weight:700">⚛️ Radar Comex (React) no ar!</div>
<div style="margin-top:8px"><a style="color:{ROXO_CLARO};font-weight:700" href="{app['url']}" target="_blank">➜ Abrir o app React</a>
&nbsp;·&nbsp;<a style="color:{ROXO_CLARO}" href="{cfg_get('app_url', '#')}" target="_blank">versão Streamlit (Lab 4)</a>
&nbsp;·&nbsp;<a style="color:{ROXO_CLARO}" href="{app['url']}/logz" target="_blank">logs</a></div></div>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎤 Roteiro da demo (3–5 min)
# MAGIC 1. Abra lado a lado a versão **Streamlit** (Lab 4) e a **React**: mesmos números, mesma fonte, mesma identidade visual.
# MAGIC 2. Na aba **Visão geral**, troque o ano e as vias: só a API é chamada (`/api/visao-geral`), sem recarregar a página.
# MAGIC 3. Na aba **Pergunte ao Genie**, faça uma pergunta: o React chama `/api/genie`, que usa a **Genie Conversation API**.
# MAGIC 4. Mostre a pasta `app_radar_comex_react`: `app.py` (FastAPI, ~200 linhas) + `static/` (React compilado).
# MAGIC 5. Mensagem: *"O time de dados prototipa em Streamlit; o time de produto entrega em React, **na mesma plataforma**,
# MAGIC    com o mesmo SSO, o mesmo service principal e as mesmas permissões do Unity Catalog. A API FastAPI também pode
# MAGIC    servir outros produtos da LogComex."*
# MAGIC
# MAGIC > O código-fonte do frontend (React + Vite) fica fora do workspace; aqui vai só o resultado compilado, então o deploy
# MAGIC > não depende de `npm install` e leva o mesmo tempo do app Streamlit.
