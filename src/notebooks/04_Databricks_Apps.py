# Databricks notebook source
# MAGIC %md
# MAGIC # 🟣 Lab 4 — Databricks Apps: o "Radar Comex" no ar
# MAGIC
# MAGIC **Tempo estimado:** 25 minutos
# MAGIC
# MAGIC Os **Databricks Apps** hospedam aplicações web (Streamlit, Dash, Gradio, Flask, FastAPI, React/Node...) **dentro**
# MAGIC do Databricks: sem servidores para gerenciar, com SSO, governança do Unity Catalog e acesso nativo a SQL Warehouses,
# MAGIC Genie, Model Serving e Lakebase.
# MAGIC
# MAGIC Nosso app **Radar Comex** (Streamlit) junta tudo o que construímos:
# MAGIC
# MAGIC | Aba | Fonte |
# MAGIC |---|---|
# MAGIC | 📊 Visão geral | `gold_comercio_exterior_mensal` via Databricks SQL |
# MAGIC | 🔎 Inteligência de NCM | `silver_importacoes` (preço/kg, países, importadores) |
# MAGIC | 🚢 Rastreamento | `gold_embarques` + `silver_eventos_embarque` |
# MAGIC | 🧞 Pergunte ao Genie | **Genie Conversation API** → o espaço do Lab 3 |
# MAGIC
# MAGIC ```
# MAGIC  Usuário ──SSO──▶ Databricks App (Streamlit) ──▶ SQL Warehouse ──▶ Tabelas Gold/Silver (Unity Catalog)
# MAGIC                         │  identidade: service principal do app
# MAGIC                         └──────────────────▶ Genie space (Lab 3)
# MAGIC ```

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4.1 Gerar o código do app na sua pasta
# MAGIC
# MAGIC A célula abaixo grava o código em `/Workspace/Users/<você>/logcomex_workshop/app_radar_comex/`.
# MAGIC Se o `app.py` já existir ele **não é sobrescrito** (para preservar suas alterações) — mude o widget
# MAGIC **recriar_codigo** para `sim` se quiser voltar à versão original.

# COMMAND ----------

import base64

APP_PY_B64 = "__APP_PY_B64__"
LOGO_B64 = "__LOGO_B64__"

dbutils.widgets.dropdown("recriar_codigo", "nao", ["nao", "sim"], "Recriar app.py original?")
w.workspace.mkdirs(PASTA_APP)
arquivo_app = f"{PASTA_APP}/app.py"
if not os.path.exists(arquivo_app) or dbutils.widgets.get("recriar_codigo") == "sim":
    with open(arquivo_app, "wb") as f:
        f.write(base64.b64decode(APP_PY_B64))
    print("📝 app.py gerado.")
else:
    print("📝 app.py já existe — mantendo a sua versão.")
with open(f"{PASTA_APP}/logo_branco.svg", "wb") as f:
    f.write(base64.b64decode(LOGO_B64))

WAREHOUSE_ID = escolher_warehouse()
GENIE_SPACE_ID = cfg_get("genie_space_id", "")
DASHBOARD_ID = cfg_get("dashboard_id", "")
DASHBOARD_URL = url_workspace(f"/dashboardsv3/{DASHBOARD_ID}/published") if DASHBOARD_ID else ""
if not GENIE_SPACE_ID:
    print("⚠️ Genie space não encontrado — rode o Lab 3 antes para habilitar a aba 'Pergunte ao Genie'.")

# app.yaml: comando de execução + configuração via variáveis de ambiente
tema = f"--theme.base=light --theme.primaryColor={ROXO} --theme.backgroundColor=#FFFFFF --theme.secondaryBackgroundColor=#F6F3FC --theme.textColor={PRETO}"
app_yaml = f"""command: {json.dumps(["streamlit", "run", "app.py"] + tema.split())}
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
"""
with open(f"{PASTA_APP}/app.yaml", "w") as f:
    f.write(app_yaml)
print(app_yaml)
displayHTML(f'📂 <a href="{url_workspace("/#workspace" + PASTA_APP.replace("/Workspace", "", 1))}" target="_blank">Abrir a pasta do app no workspace</a>')

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4.2 Permissões do app (princípio do menor privilégio)
# MAGIC
# MAGIC Todo app tem um **service principal** próprio. Damos a ele **somente** o necessário: ler o seu schema,
# MAGIC usar o warehouse e executar o Genie space.

# COMMAND ----------

def garantir_app():
    try:
        return api("GET", f"/api/2.0/apps/{APP_NAME}")
    except Exception:
        return api("POST", "/api/2.0/apps", {"name": APP_NAME, "description": "Radar Comex — app do Workshop LogComex x Databricks"})


app = garantir_app()
SP = app["service_principal_client_id"]
print(f"🤖 Service principal do app: {app.get('service_principal_name', SP)} ({SP})")

concessoes = [
    (f"GRANT USE CATALOG ON CATALOG `{CATALOGO}` TO `{SP}`", "USE CATALOG no catálogo"),
    (f"GRANT USE SCHEMA, SELECT ON SCHEMA {FQ} TO `{SP}`", "USE SCHEMA + SELECT no schema"),
]
for comando, descricao in concessoes:
    try:
        spark.sql(comando)
        print(f"✅ {descricao}")
    except Exception as erro:
        print(f"⚠️ {descricao}: {str(erro).splitlines()[0][:140]} (peça ao instrutor/admin se necessário)")

for recurso, nivel, descricao in [(f"sql/warehouses/{WAREHOUSE_ID}", "CAN_USE", "warehouse"),
                                  (f"genie/{GENIE_SPACE_ID}", "CAN_RUN", "Genie space")]:
    if recurso.endswith("/"):
        continue
    try:
        api("PATCH", f"/api/2.0/permissions/{recurso}",
            {"access_control_list": [{"service_principal_name": SP, "permission_level": nivel}]})
        print(f"✅ {nivel} no {descricao}")
    except Exception as erro:
        print(f"⚠️ {descricao}: {str(erro).splitlines()[0][:140]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4.3 Deploy 🚀
# MAGIC
# MAGIC Rode esta célula sempre que alterar o código. Ela espera o compute do app ficar pronto, envia o código e
# MAGIC acompanha o deploy (~1–3 min).

# COMMAND ----------

def aguardar_compute(limite=600):
    inicio = time.time()
    while time.time() - inicio < limite:
        estado = api("GET", f"/api/2.0/apps/{APP_NAME}").get("compute_status", {}).get("state")
        if estado == "ACTIVE":
            return
        if estado in ("STOPPED", "ERROR"):
            api("POST", f"/api/2.0/apps/{APP_NAME}/start")
        print(f"⏳ compute do app: {estado}...")
        time.sleep(15)
    raise TimeoutError("O compute do app não ficou ativo a tempo — tente novamente em instantes.")


aguardar_compute()
dep = api("POST", f"/api/2.0/apps/{APP_NAME}/deployments", {"source_code_path": PASTA_APP, "mode": "SNAPSHOT"})
while True:
    dep = api("GET", f"/api/2.0/apps/{APP_NAME}/deployments/{dep['deployment_id']}")
    estado = dep.get("status", {}).get("state")
    if estado not in ("IN_PROGRESS", "PENDING"):
        break
    print(f"⏳ deploy: {estado}...")
    time.sleep(10)

app = api("GET", f"/api/2.0/apps/{APP_NAME}")
if estado != "SUCCEEDED":
    raise RuntimeError(f"Deploy falhou: {dep.get('status', {}).get('message')} — veja os logs em {app.get('url')}/logz")
cfg_set("app_url", app["url"])
displayHTML(f"""<div style="font-family:Poppins,Arial;background:{PRETO};color:white;padding:18px 24px;border-radius:12px;border-left:8px solid {ROXO}">
<div style="font-size:20px;font-weight:700">🚀 Radar Comex no ar!</div>
<div style="margin-top:8px"><a style="color:{ROXO_CLARO};font-weight:700" href="{app['url']}" target="_blank">➜ Abrir o app</a>
&nbsp;·&nbsp;<a style="color:{ROXO_CLARO}" href="{url_workspace('/apps/' + APP_NAME)}" target="_blank">página de gestão do app</a>
&nbsp;·&nbsp;<a style="color:{ROXO_CLARO}" href="{app['url']}/logz" target="_blank">logs</a></div></div>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧭 Exercícios
# MAGIC
# MAGIC ### 1. Explore o app (5 min)
# MAGIC - Abra o app (link acima). Troque o **ano** e a **via de transporte** na barra lateral.
# MAGIC - Na aba **Inteligência de NCM**, escolha *Veículos elétricos* e depois *Módulos fotovoltaicos*: compare o preço médio US$/kg.
# MAGIC - Na aba **Rastreamento**, clique num contêiner atrasado e veja a linha do tempo de eventos.
# MAGIC - Na aba **Pergunte ao Genie**, faça uma pergunta e abra o SQL gerado — é o mesmo espaço do Lab 3, agora dentro do seu produto.
# MAGIC
# MAGIC ### 2. Altere o código e faça o redeploy (10 min)
# MAGIC 1. Abra a pasta do app (link na célula 4.1) e clique em **app.py** — o editor do workspace abre o arquivo.
# MAGIC 2. Procure por `🏁 EXERCÍCIO DO LAB 4` e **descomente** o bloco (selecione as linhas e use `Ctrl/Cmd + /`).
# MAGIC 3. Volte aqui e rode novamente a célula **4.3 Deploy**. Atualize o app: o novo gráfico de destinos das exportações aparece. 🎉
# MAGIC 4. **Desafio:** peça ao **Databricks Assistant** (✨, dentro do editor do `app.py`) para *"adicionar na aba de visão geral um
# MAGIC    gráfico de pizza com a participação de cada via de transporte no FOB importado"* e faça o deploy de novo.
# MAGIC
# MAGIC ### 3. Operação e segurança (5 min)
# MAGIC - Na **página de gestão do app**: veja *Deployments*, *Logs*, *Environment* e a aba **Permissions** — compartilhe o app com um colega (*Can use*).
# MAGIC - Discussão: o app acessa os dados como **service principal** (permissões mínimas que demos no passo 4.2).
# MAGIC   Também é possível usar a **autorização em nome do usuário** (*on-behalf-of-user*), para que cada pessoa veja apenas o que o Unity Catalog permite a ela.
# MAGIC
# MAGIC > 💡 **Para levar:** apps podem ser versionados em Git e implantados via **Databricks Asset Bundles**, servir APIs (FastAPI)
# MAGIC > para produtos externos, e usar **Lakebase** (Postgres gerenciado) para dados transacionais.
