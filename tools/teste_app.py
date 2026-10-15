# Databricks notebook source
import os, json, shutil
from streamlit.testing.v1 import AppTest
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
cfg = {r[0]: r[1] for r in spark.sql("SELECT * FROM serverless_stable_g01yyz_catalog.logcomex_ws_rafael_almeida._workshop_config").collect()}
R={}
os.environ.update({"WAREHOUSE_ID": cfg["warehouse_id"], "CATALOGO": "serverless_stable_g01yyz_catalog",
                   "SCHEMA": "logcomex_ws_rafael_almeida", "GENIE_SPACE_ID": cfg["genie_space_id"], "DASHBOARD_URL": "x",
                   "DATABRICKS_HOST": w.config.host, "DATABRICKS_TOKEN": w.config.authenticate()["Authorization"].split()[1]})
src = "/Workspace/Users/rafael.almeida@databricks.com/logcomex_workshop/app_radar_comex"
shutil.copytree(src, "/tmp/app", dirs_exist_ok=True)
at = AppTest.from_file("/tmp/app/app.py", default_timeout=180).run()
R["EXC1"]=str([e.value for e in at.exception])
R["METRICS"]=str([m.value[:110] for m in at.markdown][1:14])
R["DFS"]=str([len(d.value) for d in at.dataframe])
at.chat_input[0].set_value("Qual armador tem o maior atraso médio nas rotas vindas da Ásia?").run(timeout=240)
R["EXC2"]=str([e.value for e in at.exception])
R["ERR"]=str([e.value for e in at.error])
R["CHAT"]=str([m.value[:400] for m in at.markdown][-6:])
R["CODE"]=str([c.value for c in at.code])
dbutils.notebook.exit(json.dumps(R, ensure_ascii=False))
