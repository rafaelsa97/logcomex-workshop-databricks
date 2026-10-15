#!/usr/bin/env python3
"""Consulta as métricas de referência no workspace e preenche roteiro.html -> roteiro_final.html."""
import json, os, subprocess, sys
from pathlib import Path

P = "fe-vm-fevm-serverless-stable-g01yyz"
WH = "51b21ad779332b37"
T = "serverless_stable_g01yyz_catalog.logcomex_ws_rafael_almeida"
os.environ["DATABRICKS_AUTH_STORAGE"] = "plaintext"


def q(sql):
    body = json.dumps({"statement": sql, "warehouse_id": WH, "wait_timeout": "50s"})
    out = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--json", body, "-p", P],
                         capture_output=True, text=True, check=True).stdout
    r = json.loads(out)
    if r["status"]["state"] != "SUCCEEDED":
        sys.exit(f"{sql}\n{r['status']}")
    return r["result"]["data_array"][0]


def usd(v):
    v = float(v)
    for lim, suf in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"US$ {v/lim:,.1f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {v:,.0f}"


def n(v):
    return f"{int(float(v)):,}".replace(",", ".")


def dec(v):
    return f"{float(v):.1f}".replace(".", ",")


M = {}
ev = q(f"SELECT sum(IF(year(data_registro)=2024,valor_fob_usd,0)), sum(IF(year(data_registro)=2025,valor_fob_usd,0)), sum(IF(year(data_registro)=2026,valor_fob_usd,0)) FROM {T}.silver_importacoes WHERE ncm='8703.80.00'")
M["EV_2024"], M["EV_2025"], M["EV_2026"] = map(usd, ev)
pg = q(f"SELECT avg(IF(data_registro<'2026-06-01',dias_desembaraco,NULL)), avg(IF(data_registro>='2026-06-01',dias_desembaraco,NULL)), avg(IF(data_registro<'2026-06-01',IF(canal_parametrizacao='Vermelho',1,0),NULL)), avg(IF(data_registro>='2026-06-01',IF(canal_parametrizacao='Vermelho',1,0),NULL)) FROM {T}.silver_importacoes WHERE urf_despacho='Porto de Paranaguá'")
M["PGUA_ANTES"], M["PGUA_DEPOIS"] = dec(pg[0]), dec(pg[1])
M["PGUA_VERM_ANTES"], M["PGUA_VERM_DEPOIS"] = f"{float(pg[2])*100:.0f}%", f"{float(pg[3])*100:.0f}%"
ar = q(f"SELECT armador, avg(atraso_dias) a FROM {T}.gold_embarques GROUP BY armador ORDER BY a DESC LIMIT 1")
M["ARMADOR_PIOR"], M["ARMADOR_PIOR_DIAS"] = ar[0], dec(ar[1])
M["ARMADOR_MEDIA_DIAS"] = dec(q(f"SELECT avg(atraso_dias) FROM {T}.gold_embarques WHERE armador <> '{ar[0]}'")[0])
M["ARMADOR_PIOR_ASIA"] = dec(q(f"SELECT avg(atraso_dias) FROM {T}.gold_embarques WHERE armador='{ar[0]}' AND porto_origem IN ('Xangai','Ningbo','Shenzhen','Qingdao','Ho Chi Minh','Busan','Yokohama','Kaohsiung','Jacarta')")[0])
c = q(f"SELECT (SELECT count(*) FROM {T}.bronze_importacoes), (SELECT count(*) FROM {T}.bronze_importacoes WHERE _arquivo_origem='importacoes_2026_09.csv'), (SELECT count(*) FROM {T}.silver_importacoes), (SELECT count(*) FROM {T}.silver_importacoes_rejeitadas), (SELECT count(DISTINCT pais_origem) FROM {T}.bronze_importacoes), (SELECT count(DISTINCT pais_origem) FROM {T}.silver_importacoes), (SELECT count(*) FROM {T}.bronze_exportacoes), (SELECT count(*) FROM {T}.bronze_eventos_embarque), (SELECT count(*) FROM {T}.silver_exportacoes), (SELECT count(*) FROM {T}.silver_eventos_embarque), (SELECT count(*) FROM {T}.gold_comercio_exterior_mensal), (SELECT count(*) FROM {T}.gold_desempenho_portos), (SELECT count(*) FROM {T}.gold_embarques)")
(M["QTD_DIS"], M["BRONZE_NOVAS"], M["SILVER_VALIDAS"], M["SILVER_REJ"], M["PAISES_SUJOS"], M["PAISES_LIMPOS"], M["QTD_DUES"], M["QTD_EVENTOS"],
 M["QTD_SILVER_EXP"], M["QTD_SILVER_EV"], M["QTD_GOLD_COM"], M["QTD_GOLD_PORTOS"], M["QTD_GOLD_EMB"]) = map(n, c)
M["BRONZE_ANTES"] = n(int(c[0]) - int(c[1]))
t = q(f"SELECT sum(IF(fluxo='Importação',valor_fob_usd,0)), sum(IF(fluxo='Exportação',valor_fob_usd,0)), sum(qtd_operacoes) FROM {T}.gold_comercio_exterior_mensal")
M["FOB_IMP"], M["FOB_EXP"], M["SALDO"], M["OPERACOES"] = usd(t[0]), usd(t[1]), usd(float(t[1]) - float(t[0])), n(t[2])
d = q(f"SELECT avg(dias_desembaraco), avg(IF(canal_parametrizacao='Vermelho',1,0)), sum(IF(year(data_registro)=2025,valor_fob_usd,0)) FROM {T}.silver_importacoes")
M["DIAS_GERAL"], M["PCT_VERM"], M["FOB_IMP_2025"] = dec(d[0]), f"{float(d[1])*100:.1f}%".replace(".", ","), usd(d[2])
M["OP_CRITICAS"] = n(q(f"SELECT count(*) FROM {T}.silver_importacoes WHERE canal_parametrizacao IN ('Vermelho','Cinza') AND valor_fob_usd > 1000000 AND year(data_registro)=2026")[0])
M["TOP_EV_IMPORTADOR"] = q(f"SELECT razao_social_importador FROM {T}.silver_importacoes WHERE ncm='8703.80.00' AND year(data_registro)=2026 GROUP BY 1 ORDER BY sum(valor_fob_usd) DESC LIMIT 1")[0]

print(json.dumps(M, indent=1, ensure_ascii=False))
raiz = Path(__file__).resolve().parent.parent / "roteiro"
html = (raiz / "roteiro.html").read_text()
for k, v in M.items():
    html = html.replace("{{" + k + "}}", str(v))
assert "{{" not in html, [l for l in html.splitlines() if "{{" in l]
(raiz / "roteiro_final.html").write_text(html)
