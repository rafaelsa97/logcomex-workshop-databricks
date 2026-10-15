# Databricks notebook source
# MAGIC %md
# MAGIC # 🟣 Lab 2 — AI/BI Dashboards
# MAGIC
# MAGIC **Tempo estimado:** 30 minutos
# MAGIC
# MAGIC Os **AI/BI Dashboards** são o BI nativo do Databricks: rodam direto sobre as tabelas do Unity Catalog
# MAGIC (sem extrações nem cópias), herdam as permissões de governança e trazem IA para criar visualizações a partir de
# MAGIC linguagem natural.
# MAGIC
# MAGIC **Neste lab:**
# MAGIC 1. ▶️ Rode a célula abaixo — ela cria automaticamente o dashboard **"Radar Comex"** (2 páginas, identidade visual LogComex).
# MAGIC 2. 🧭 Explore o dashboard: filtros globais, *cross-filtering*, *drill* em gráficos.
# MAGIC 3. ✏️ Edite: crie novos gráficos **com IA**, adicione um filtro, ajuste o tema.
# MAGIC 4. 📤 Publique, compartilhe e agende o envio por e-mail.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

WAREHOUSE_ID = escolher_warehouse()
T = f"{CATALOGO}.{SCHEMA}"
assert spark.catalog.tableExists(f"{T}.gold_embarques"), "⚠️ Tabelas Gold não encontradas. Conclua o Lab 1 (ou rode o 00_Setup com fast_track = sim)."

# ------------------------------------------------------------------ datasets (consultas SQL do dashboard)
DATASETS = {
    "ds_comercio": ("Comércio exterior mensal", f"""
        SELECT mes, fluxo, ncm, descricao_ncm, categoria_ncm, pais_parceiro, uf, porto, via_transporte,
               qtd_operacoes, valor_fob_usd, toneladas,
               IF(fluxo = 'Importação', valor_fob_usd, 0) AS fob_importado_usd,
               IF(fluxo = 'Exportação', valor_fob_usd, 0) AS fob_exportado_usd,
               IF(fluxo = 'Exportação', valor_fob_usd, -valor_fob_usd) AS saldo_usd
        FROM {T}.gold_comercio_exterior_mensal"""),
    "ds_importacoes": ("DIs de importação", f"""
        SELECT mes_registro AS mes, numero_di, razao_social_importador, uf_importador, setor_importador,
               categoria_ncm, descricao_ncm, pais_origem, urf_despacho AS porto, via_transporte,
               canal_parametrizacao, dias_desembaraco, valor_fob_usd,
               IF(canal_parametrizacao = 'Vermelho', 1, 0) AS flag_canal_vermelho
        FROM {T}.silver_importacoes"""),
    "ds_embarques": ("Embarques rastreados", f"""
        SELECT CAST(date_trunc('MONTH', data_partida) AS DATE) AS mes, 'Marítima' AS via_transporte,
               container, armador, navio, porto_origem, porto_destino, consignatario, eta_prevista,
               transit_time_dias, atraso_dias, status_embarque,
               IF(status_embarque = 'Em trânsito - atrasado', 1, 0) AS flag_atrasado
        FROM {T}.gold_embarques"""),
}

USD = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
DIAS = {"type": "number-plain", "abbreviation": "none", "decimalPlaces": {"type": "max", "places": 1}}
CORES_FLUXO = [{"value": "Importação", "color": ROXO}, {"value": "Exportação", "color": PRETO}]
CORES_CANAL = [{"value": "Verde", "color": "#1F9D55"}, {"value": "Amarelo", "color": "#F2B705"},
               {"value": "Vermelho", "color": "#E03E3E"}, {"value": "Cinza", "color": "#9CA3AF"}]


def campo(nome, expr=None):
    return {"name": nome, "expression": expr or f"`{nome}`"}


def widget(nome, dataset, campos, spec, pos, desagregado=False):
    return {"widget": {"name": nome,
                       "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": campos, "disaggregated": desagregado}}],
                       "spec": spec},
            "position": dict(zip(["x", "y", "width", "height"], pos))}


def texto(nome, linhas, pos):
    return {"widget": {"name": nome, "multilineTextboxSpec": {"lines": linhas}}, "position": dict(zip(["x", "y", "width", "height"], pos))}


def titulo(t, descricao=None):
    f = {"showTitle": True, "title": t}
    if descricao:
        f.update({"description": descricao, "showDescription": True})
    return f


def kpi(nome, dataset, coluna, agg, rotulo, fmt, pos, descricao=None):
    fid = f"{agg.lower()}({coluna})"
    return widget(nome, dataset, [campo(fid, f"{agg}(`{coluna}`)"), campo("monthly(mes)", 'DATE_TRUNC("MONTH", `mes`)')],
                  {"version": 2, "widgetType": "counter",
                   "encodings": {"value": {"fieldName": fid, "displayName": rotulo, "format": fmt, "color": {"hex": ROXO}},
                                 "period": {"fieldName": "monthly(mes)"}},
                   "frame": titulo(rotulo, descricao)}, pos)


def barra(nome, dataset, cat, medida, agg, rotulo_cat, rotulo_med, fmt, pos, cor=None, mapeamento=None, desc=None):
    fid = f"{agg.lower()}({medida})"
    campos = [campo(cat), campo(fid, f"{agg}(`{medida}`)")] + ([campo(cor)] if cor else [])
    enc = {"x": {"fieldName": fid, "displayName": rotulo_med, "format": fmt, "scale": {"type": "quantitative"}},
           "y": {"fieldName": cat, "displayName": rotulo_cat, "scale": {"type": "categorical", "sort": {"by": "x-reversed"}}}}
    if cor:
        enc["color"] = {"fieldName": cor, "displayName": cor.replace("_", " ").title(),
                        "scale": {"type": "categorical", **({"mappings": mapeamento} if mapeamento else {})}}
    return widget(nome, dataset, campos, {"version": 3, "widgetType": "bar", "mark": {"layout": "stack"},
                                          "encodings": enc, "frame": titulo(rotulo_med + " por " + rotulo_cat.lower() if not desc else desc[0], desc[1] if desc else None)}, pos)


def linha(nome, dataset, medida, agg, cor, rotulo, fmt, pos, mapeamento, desc):
    fid = f"{agg.lower()}({medida})"
    return widget(nome, dataset, [campo("monthly(mes)", 'DATE_TRUNC("MONTH", `mes`)'), campo(fid, f"{agg}(`{medida}`)"), campo(cor)],
                  {"version": 3, "widgetType": "line",
                   "encodings": {"x": {"fieldName": "monthly(mes)", "displayName": "Mês", "scale": {"type": "temporal"}},
                                 "y": {"fieldName": fid, "displayName": rotulo, "format": fmt, "scale": {"type": "quantitative"}},
                                 "color": {"fieldName": cor, "displayName": cor.replace("_", " ").title(),
                                           "scale": {"type": "categorical", "mappings": mapeamento}}},
                   "frame": titulo(*desc)}, pos)


# ------------------------------------------------------------------ página 1: visão geral
PORTOS_CINZA = ["Porto de Santos", "Porto de Itajaí", "Porto de Navegantes", "Porto de Rio Grande", "Porto do Rio de Janeiro",
                "Porto de Suape", "Porto de Vitória", "Porto de Manaus", "Porto de Salvador"]
CORES_PORTO = [{"value": "Porto de Paranaguá", "color": ROXO}] + [
    {"value": p, "color": c} for p, c in zip(PORTOS_CINZA, ["#3F3F46", "#52525B", "#71717A", "#A1A1AA", "#D4D4D8", "#C4B5FD", "#9CA3AF", "#6B7280", "#E4E4E7"])]

pagina_visao = [
    texto("cabecalho", [
        "# **logcomex**.ai · Radar do Comércio Exterior\n",
        "Visão consolidada das **importações (DI)** e **exportações (DU-E)** brasileiras — jan/2024 a set/2026. ",
        "Use os filtros à esquerda (período, via de transporte, categoria) e clique em qualquer barra para filtrar o restante da página. ",
        "*Dados 100% sintéticos gerados para o Workshop LogComex × Databricks.*"], (0, 0, 12, 2)),
    kpi("kpi_fob_import", "ds_comercio", "fob_importado_usd", "SUM", "FOB importado (US$)", USD, (0, 2, 3, 3)),
    kpi("kpi_fob_export", "ds_comercio", "fob_exportado_usd", "SUM", "FOB exportado (US$)", USD, (3, 2, 3, 3)),
    kpi("kpi_saldo", "ds_comercio", "saldo_usd", "SUM", "Saldo da balança (US$)", USD, (6, 2, 3, 3)),
    kpi("kpi_operacoes", "ds_comercio", "qtd_operacoes", "SUM", "Operações (DIs + DU-Es)",
        {"type": "number-plain", "abbreviation": "compact"}, (9, 2, 3, 3)),
    linha("linha_fluxo", "ds_comercio", "valor_fob_usd", "SUM", "fluxo", "Valor FOB (US$)", USD, (0, 5, 8, 6), CORES_FLUXO,
          ("Evolução mensal: importação × exportação", "Valor FOB mensal em dólares por fluxo de comércio.")),
    barra("barra_paises", "ds_importacoes", "pais_origem", "valor_fob_usd", "SUM", "País de origem", "FOB importado (US$)", USD,
          (8, 5, 4, 6), desc=("De onde vêm as importações", None)),
    barra("barra_categorias", "ds_importacoes", "categoria_ncm", "valor_fob_usd", "SUM", "Categoria NCM", "FOB importado (US$)", USD,
          (0, 11, 6, 6), cor="via_transporte", desc=("FOB importado por categoria e via de transporte", None)),
    widget("tabela_importadores", "ds_importacoes",
           [campo("razao_social_importador"), campo("uf_importador"), campo("setor_importador"),
            campo("countdistinct(numero_di)", "COUNT(DISTINCT `numero_di`)"), campo("sum(valor_fob_usd)", "SUM(`valor_fob_usd`)")],
           {"version": 2, "widgetType": "table",
            "encodings": {"columns": [{"fieldName": "razao_social_importador", "displayName": "Importador"},
                                      {"fieldName": "uf_importador", "displayName": "UF"},
                                      {"fieldName": "setor_importador", "displayName": "Setor"},
                                      {"fieldName": "countdistinct(numero_di)", "displayName": "DIs"},
                                      {"fieldName": "sum(valor_fob_usd)", "displayName": "FOB (US$)", "format": USD}]},
            "frame": titulo("Maiores importadores")}, (6, 11, 6, 6)),
]

# ------------------------------------------------------------------ página 2: logística e desembaraço
pagina_logistica = [
    texto("cabecalho_log", [
        "# Logística e desembaraço aduaneiro\n",
        "Quanto tempo as cargas levam para serem liberadas pela Receita Federal e como os armadores estão cumprindo as ETAs. ",
        "🔎 **Repare no porto destacado em roxo no gráfico de tempo de desembaraço** — e no ranking de atraso por armador."], (0, 0, 12, 2)),
    kpi("kpi_dias", "ds_importacoes", "dias_desembaraco", "AVG", "Tempo médio de desembaraço (dias)", DIAS, (0, 2, 3, 3)),
    kpi("kpi_vermelho", "ds_importacoes", "flag_canal_vermelho", "AVG", "DIs em canal vermelho", PCT, (3, 2, 3, 3)),
    kpi("kpi_transit", "ds_embarques", "transit_time_dias", "AVG", "Transit time médio (dias)", DIAS, (6, 2, 3, 3)),
    kpi("kpi_atrasados", "ds_embarques", "flag_atrasado", "SUM", "Contêineres em trânsito atrasados",
        {"type": "number-plain", "abbreviation": "none"}, (9, 2, 3, 3)),
    linha("linha_desembaraco", "ds_importacoes", "dias_desembaraco", "AVG", "porto", "Dias até o desembaraço", DIAS, (0, 5, 12, 6),
          CORES_PORTO, ("Tempo médio de desembaraço por porto (dias)", "Dias entre o registro da DI e o desembaraço. Paranaguá em destaque.")),
    barra("barra_canais", "ds_importacoes", "porto", "numero_di", "COUNT", "Local de despacho", "Quantidade de DIs",
          {"type": "number-plain", "abbreviation": "compact"}, (0, 11, 6, 7), cor="canal_parametrizacao", mapeamento=CORES_CANAL,
          desc=("Canais de parametrização por local de despacho", "Verde = liberação automática · Amarelo = documental · Vermelho = física · Cinza = valoração.")),
    barra("barra_armadores", "ds_embarques", "armador", "atraso_dias", "AVG", "Armador", "Atraso médio (dias)", DIAS, (6, 11, 6, 7),
          desc=("Atraso médio em relação à ETA por armador", None)),
    widget("tabela_atrasados", "ds_embarques",
           [campo(c) for c in ["container", "armador", "navio", "porto_origem", "porto_destino", "consignatario", "eta_prevista", "atraso_dias", "status_embarque"]],
           {"version": 2, "widgetType": "table",
            "encodings": {"columns": [{"fieldName": c, "displayName": d} for c, d in [
                ("container", "Contêiner"), ("armador", "Armador"), ("navio", "Navio"), ("porto_origem", "Origem"),
                ("porto_destino", "Destino"), ("consignatario", "Consignatário"), ("eta_prevista", "ETA prevista"),
                ("atraso_dias", "Atraso (dias)"), ("status_embarque", "Status")]]},
            "frame": titulo("Detalhe dos contêineres rastreados")}, (0, 18, 12, 7), desagregado=True),
]


# ------------------------------------------------------------------ filtros globais
def filtro(nome, tipo, coluna, datasets, rotulo, pos, extra=None):
    queries, campos = [], []
    for ds in datasets:
        qn = f"filtro_{nome}_{ds}"
        queries.append({"name": qn, "query": {"datasetName": ds, "fields": [campo(coluna), campo(f"{coluna}_associativity", "COUNT_IF(`associative_filter_predicate_group`)")], "disaggregated": False}})
        campos.append({"fieldName": coluna, "queryName": qn})
    spec = {"version": 2, "widgetType": tipo, "encodings": {"fields": campos}, "frame": {"showTitle": True, "title": rotulo}}
    spec.update(extra or {})
    return {"widget": {"name": nome, "queries": queries, "spec": spec}, "position": dict(zip(["x", "y", "width", "height"], pos))}


pagina_filtros = [
    filtro("f_periodo", "filter-date-range-picker", "mes", ["ds_comercio", "ds_importacoes", "ds_embarques"], "Período", (0, 0, 1, 2)),
    filtro("f_via", "filter-multi-select", "via_transporte", ["ds_comercio", "ds_importacoes", "ds_embarques"], "Via de transporte", (0, 2, 1, 2)),
    filtro("f_categoria", "filter-multi-select", "categoria_ncm", ["ds_comercio", "ds_importacoes"], "Categoria NCM", (0, 4, 1, 2)),
]

dashboard = {
    "datasets": [{"name": n, "displayName": d, "queryLines": [q.strip()]} for n, (d, q) in DATASETS.items()],
    "pages": [
        {"name": "visao_geral", "displayName": "Visão geral", "layout": pagina_visao, "pageType": "PAGE_TYPE_CANVAS"},
        {"name": "logistica", "displayName": "Logística e desembaraço", "layout": pagina_logistica, "pageType": "PAGE_TYPE_CANVAS"},
        {"name": "filtros", "displayName": "Filtros", "layout": pagina_filtros, "pageType": "PAGE_TYPE_GLOBAL_FILTERS"},
    ],
    "uiSettings": {"theme": {
        "canvasBackgroundColor": {"light": "#F6F3FC", "dark": PRETO},
        "widgetBackgroundColor": {"light": BRANCO, "dark": "#161827"},
        "widgetBorderColor": {"light": BRANCO, "dark": "#161827"},
        "fontColor": {"light": PRETO, "dark": "#F4F1FA"},
        "selectionColor": {"light": ROXO, "dark": ROXO_CLARO},
        "visualizationColors": [ROXO, PRETO, ROXO_CLARO, "#3F3F46", "#9F67F5", "#A1A1AA", ROXO_ESCURO, "#D8C7F7"],
        "widgetHeaderAlignment": "LEFT",
    }},
}

# ------------------------------------------------------------------ cria (ou atualiza) e publica
nome_dash = f"Radar Comex — LogComex Workshop ({SLUG})"
corpo = {"display_name": nome_dash, "warehouse_id": WAREHOUSE_ID, "serialized_dashboard": json.dumps(dashboard, ensure_ascii=False),
         "parent_path": PASTA_USUARIO}
w.workspace.mkdirs(PASTA_USUARIO)
dash_id = cfg_get("dashboard_id")
try:
    if not dash_id:
        raise LookupError
    api("PATCH", f"/api/2.0/lakeview/dashboards/{dash_id}", {k: v for k, v in corpo.items() if k != "parent_path"})
except Exception:
    dash_id = api("POST", "/api/2.0/lakeview/dashboards", corpo)["dashboard_id"]
    cfg_set("dashboard_id", dash_id)
api("POST", f"/api/2.0/lakeview/dashboards/{dash_id}/published", {"embed_credentials": True, "warehouse_id": WAREHOUSE_ID})

URL_DASH = url_workspace(f"/dashboardsv3/{dash_id}/published")
displayHTML(f"""<div style="font-family:Poppins,Arial;background:{PRETO};color:white;padding:18px 24px;border-radius:12px;border-left:8px solid {ROXO}">
<div style="font-size:20px;font-weight:700">📊 Dashboard criado e publicado!</div>
<div style="margin-top:8px"><a style="color:{ROXO_CLARO};font-weight:700" href="{URL_DASH}" target="_blank">➜ Abrir o Radar Comex</a>
&nbsp;·&nbsp;<a style="color:{ROXO_CLARO}" href="{url_workspace(f'/dashboardsv3/{dash_id}')}" target="_blank">abrir em modo edição</a></div></div>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧭 Exercícios (siga na ordem)
# MAGIC
# MAGIC ### 1. Explorar (5 min)
# MAGIC - Na página **Visão geral**, clique na barra **China** do gráfico de países → toda a página é filtrada (*cross-filter*).
# MAGIC - No painel de filtros à esquerda, selecione a categoria **Automotivo**. O que acontece com a importação a partir de 2025? 🚗⚡
# MAGIC - Na página **Logística e desembaraço**, qual porto se destaca no tempo de desembaraço desde jun/2026? E qual armador tem o maior atraso médio?
# MAGIC
# MAGIC ### 2. Criar visualizações com IA (10 min)
# MAGIC Clique em **Edit draft** (canto superior direito) e:
# MAGIC 1. Na barra inferior, clique em **Add a visualization** e posicione o widget na página.
# MAGIC 2. No painel do widget, use o campo **"Ask the Assistant"** (✨) e peça, por exemplo:
# MAGIC    - *"Gráfico de barras com as 10 NCMs com maior valor FOB importado"* (dataset **DIs de importação**)
# MAGIC    - *"Valor FOB exportado por país parceiro"* (dataset **Comércio exterior mensal**)
# MAGIC 3. Ajuste título, cores e formato (US$) no painel à direita.
# MAGIC
# MAGIC ### 3. Novo dataset em SQL (5 min)
# MAGIC Na aba **Data**, clique em **+ Create from SQL** e cole:
# MAGIC ```sql
# MAGIC SELECT descricao_ncm, pais_origem, round(avg(preco_medio_usd_kg), 2) AS preco_medio_usd_kg, count(*) AS dis
# MAGIC FROM silver_importacoes GROUP BY ALL HAVING dis > 20
# MAGIC ```
# MAGIC *(use o seletor de catálogo/schema do editor apontando para o seu schema `logcomex_ws_...`)*. Crie com ele uma
# MAGIC tabela ou um *scatter* de **preço médio US$/kg por país de origem** — um clássico de inteligência de mercado.
# MAGIC
# MAGIC ### 4. Publicar e distribuir (5 min)
# MAGIC - **Publish** → publique com **credenciais embutidas** (quem recebe vê os dados com as suas permissões) ou sem (cada um vê o que pode ver no Unity Catalog).
# MAGIC - **Share** → compartilhe com um colega do workshop.
# MAGIC - **Schedule** → agende o envio do dashboard por e-mail toda segunda-feira às 8h.
# MAGIC
# MAGIC > 💡 **Para levar:** os dashboards podem ser **embarcados** em aplicações externas (portal do cliente, por exemplo),
# MAGIC > versionados em Git e implantados via **Databricks Asset Bundles**.
