# Databricks notebook source
# MAGIC %md
# MAGIC # 🧹 Limpeza do ambiente do workshop (opcional)
# MAGIC
# MAGIC Remove **somente** o que foi criado para você neste workshop: o app, o Genie space, o dashboard e o schema
# MAGIC `logcomex_ws_<seu_usuario>` (tabelas + volume). Mude o widget **confirmar** para `sim` e rode tudo.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

dbutils.widgets.dropdown("confirmar", "nao", ["nao", "sim"], "Confirmar remoção?")
if dbutils.widgets.get("confirmar") != "sim":
    dbutils.notebook.exit("Nada removido — mude o widget 'confirmar' para 'sim'.")

for descricao, metodo, caminho in [
    ("App", "DELETE", f"/api/2.0/apps/{APP_NAME}"),
    ("App React (demo do instrutor)", "DELETE", f"/api/2.0/apps/{re.sub(r'-+', '-', 'radar-react-' + SLUG.replace('_', '-'))[:30].strip('-')}"),
    ("Genie space", "DELETE", f"/api/2.0/genie/spaces/{cfg_get('genie_space_id', 'x')}"),
    ("Dashboard", "DELETE", f"/api/2.0/lakeview/dashboards/{cfg_get('dashboard_id', 'x')}"),
]:
    try:
        api(metodo, caminho)
        print(f"🗑️ {descricao} removido")
    except Exception as erro:
        print(f"– {descricao}: {str(erro).splitlines()[0][:120]}")
spark.sql(f"DROP SCHEMA IF EXISTS {FQ} CASCADE")
print(f"🗑️ Schema {CATALOGO}.{SCHEMA} removido")
