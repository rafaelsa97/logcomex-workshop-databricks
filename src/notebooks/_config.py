# Databricks notebook source
# MAGIC %md
# MAGIC # ⚙️ Configuração compartilhada do workshop
# MAGIC
# MAGIC Este notebook é executado automaticamente pelos demais (via `%run ./_config`).
# MAGIC Ele define **nomes de catálogo, schema, volume, warehouse e app** de forma
# MAGIC determinística a partir do seu usuário — assim cada participante tem o seu
# MAGIC próprio ambiente isolado, mesmo que todos usem o mesmo workspace.
# MAGIC
# MAGIC > Você não precisa alterar nada aqui. Se quiser usar outro catálogo, troque o
# MAGIC > valor do widget **catalogo** no topo do notebook que estiver executando.

# COMMAND ----------

import json
import os
import re
import time

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

USUARIO = spark.sql("SELECT current_user()").first()[0]
SLUG = re.sub(r"[^a-z0-9]+", "_", USUARIO.split("@")[0].lower()).strip("_")[:20].strip("_")


def _catalogo_padrao():
    """Catálogo atual do workspace; evita hive_metastore (sem Unity Catalog)."""
    atual = spark.sql("SELECT current_catalog()").first()[0]
    if atual and atual not in ("hive_metastore", "spark_catalog", "samples", "system"):
        return atual
    catalogos = [r[0] for r in spark.sql("SHOW CATALOGS").collect()]
    for candidato in ("workspace", "main"):
        if candidato in catalogos:
            return candidato
    return atual


dbutils.widgets.text("catalogo", _catalogo_padrao(), "Catálogo (Unity Catalog)")
CATALOGO = dbutils.widgets.get("catalogo").strip() or _catalogo_padrao()
SCHEMA = f"logcomex_ws_{SLUG}"
FQ = f"`{CATALOGO}`.`{SCHEMA}`"
VOLUME = "landing"
LANDING = f"/Volumes/{CATALOGO}/{SCHEMA}/{VOLUME}"
CHECKPOINTS = f"{LANDING}/_checkpoints"

APP_NAME = re.sub(r"-+", "-", f"radar-comex-{SLUG.replace('_', '-')}")[:30].strip("-")
PASTA_USUARIO = f"/Workspace/Users/{USUARIO}/logcomex_workshop"
PASTA_APP = f"{PASTA_USUARIO}/app_radar_comex"

# Paleta LogComex (usada no dashboard e no app)
ROXO, ROXO_ESCURO, ROXO_CLARO, PRETO, BRANCO = "#6613D0", "#4A0E99", "#B48BF0", "#0B0D19", "#FFFFFF"

# COMMAND ----------

def api(method, path, body=None, query=None):
    """Chamada REST autenticada ao workspace (independe da versão do SDK)."""
    return w.api_client.do(method, path, body=body, query=query) or {}


def cfg_tabela():
    return f"{FQ}._workshop_config"


def cfg_set(chave, valor):
    spark.sql(f"CREATE TABLE IF NOT EXISTS {cfg_tabela()} (chave STRING, valor STRING)")
    spark.sql(
        f"MERGE INTO {cfg_tabela()} t USING (SELECT :k AS chave, :v AS valor) s "
        "ON t.chave = s.chave WHEN MATCHED THEN UPDATE SET valor = s.valor "
        "WHEN NOT MATCHED THEN INSERT *",
        args={"k": chave, "v": str(valor)},
    )


def cfg_get(chave, padrao=None):
    try:
        linha = spark.sql(f"SELECT valor FROM {cfg_tabela()} WHERE chave = :k", args={"k": chave}).first()
        return linha[0] if linha else padrao
    except Exception:
        return padrao


def escolher_warehouse():
    """Reaproveita um SQL Warehouse existente (preferindo serverless); cria um 2X-Small se não houver."""
    salvo = cfg_get("warehouse_id")
    if salvo:
        return salvo
    whs = list(w.warehouses.list())

    def nota(x):
        estado = str(getattr(x.state, "value", x.state))
        return (bool(x.enable_serverless_compute), estado == "RUNNING")

    if whs:
        escolhido = sorted(whs, key=nota, reverse=True)[0].id
    else:
        criado = api("POST", "/api/2.0/sql/warehouses", {
            "name": "LogComex Workshop", "cluster_size": "2X-Small", "max_num_clusters": 1,
            "auto_stop_mins": 10, "enable_serverless_compute": True, "warehouse_type": "PRO",
        })
        escolhido = criado["id"]
    cfg_set("warehouse_id", escolhido)
    return escolhido


def url_workspace(caminho=""):
    return f"{w.config.host.rstrip('/')}{caminho}"


def resumo():
    print(f"👤 Usuário ........ {USUARIO}")
    print(f"📚 Catálogo ....... {CATALOGO}")
    print(f"🗂️  Schema ......... {SCHEMA}")
    print(f"📦 Volume ......... {LANDING}")
    print(f"🚀 App ............ {APP_NAME}")
