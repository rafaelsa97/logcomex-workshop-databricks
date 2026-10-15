# Databricks notebook source
# MAGIC %md
# MAGIC # 🎓 Preparação do instrutor (rodar 1x, antes do workshop)
# MAGIC
# MAGIC **Só é necessário quando vários participantes compartilham o MESMO workspace.** Se cada participante usa o
# MAGIC próprio workspace (como administrador), pule este notebook.
# MAGIC
# MAGIC Executado por um **admin do workspace / dono do catálogo**, ele:
# MAGIC 1. Concede `USE CATALOG` + `CREATE SCHEMA` no catálogo do workshop para todos os usuários (cada um cria o próprio schema).
# MAGIC 2. Concede `CAN_USE` no SQL Warehouse para todos os usuários (o service principal de cada app também herda via grupo `users`).
# MAGIC 3. Verifica se Genie, Apps e compute serverless estão disponíveis.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

WAREHOUSE_ID = escolher_warehouse()
for comando in [f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG `{CATALOGO}` TO `account users`"]:
    spark.sql(comando)
    print("✅", comando)
api("PATCH", f"/api/2.0/permissions/sql/warehouses/{WAREHOUSE_ID}",
    {"access_control_list": [{"group_name": "users", "permission_level": "CAN_USE"}]})
print(f"✅ CAN_USE no warehouse {WAREHOUSE_ID} para o grupo users")

apps = api("GET", "/api/2.0/apps").get("apps", [])
print(f"ℹ️ Apps existentes no workspace: {len(apps)} (cada participante cria 1 app — verifique o limite do workspace)")
api("GET", "/api/2.0/genie/spaces")
print("✅ Genie disponível")
