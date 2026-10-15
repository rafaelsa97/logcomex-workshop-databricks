# Databricks notebook source
# MAGIC %md
# MAGIC # 🟣 Lab 3 — AI/BI Genie: converse com os dados de comércio exterior
# MAGIC
# MAGIC **Tempo estimado:** 30 minutos
# MAGIC
# MAGIC O **Genie** permite que qualquer pessoa faça perguntas em **português** sobre os dados e receba respostas com
# MAGIC tabelas, gráficos e o SQL gerado — tudo respeitando as permissões do Unity Catalog. A qualidade vem de um
# MAGIC **espaço curado** pelo time de dados: tabelas escolhidas, comentários de colunas (Lab 1), instruções de negócio,
# MAGIC exemplos de SQL e *benchmarks*.
# MAGIC
# MAGIC **Neste lab:**
# MAGIC 1. ▶️ Rode a célula abaixo — ela cria o *Genie space* **"Radar Comex"** já curado com o vocabulário de comex.
# MAGIC 2. 💬 Faça perguntas, inspecione o SQL e peça gráficos.
# MAGIC 3. 🧠 Ensine um novo conceito de negócio ao Genie e valide com *benchmarks*.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from uuid import uuid4

WAREHOUSE_ID = escolher_warehouse()
T = f"{CATALOGO}.{SCHEMA}"
assert spark.catalog.tableExists(f"{T}.gold_embarques"), "⚠️ Tabelas Gold não encontradas. Conclua o Lab 1 (ou rode o 00_Setup com fast_track = sim)."

TABELAS = ["gold_comercio_exterior_mensal", "gold_desempenho_portos", "gold_embarques",
           "silver_empresas", "silver_exportacoes", "silver_importacoes", "silver_ncm"]

INSTRUCOES = f"""Você é o assistente de inteligência de comércio exterior da LogComex. Responda sempre em português do Brasil,
de forma objetiva: comece pela resposta e deixe claros os filtros, o período e a unidade usados.

GLOSSÁRIO DE COMEX
- DI / DUIMP = Declaração de Importação (tabela silver_importacoes, uma linha por DI). DU-E = Declaração Única de Exportação (silver_exportacoes).
- FOB = valor da mercadoria sem frete e seguro (valor_fob_usd). CIF = FOB + frete + seguro (valor_cif_usd).
- Balança comercial / saldo = FOB exportado - FOB importado (use gold_comercio_exterior_mensal, coluna fluxo).
- Canal de parametrização: Verde (liberação automática), Amarelo (conferência documental), Vermelho (documental + física), Cinza (valoração aduaneira).
- Lead time aduaneiro / tempo de desembaraço = dias_desembaraco (registro da DI até o desembaraço).
- Transit time = dias entre partida e chegada do navio (gold_embarques.transit_time_dias). Atraso = atraso_dias vs. ETA prevista.
- URF de despacho = porto, aeroporto ou fronteira onde a DI é despachada.
- "Ásia" = portos de origem Xangai, Ningbo, Shenzhen, Qingdao, Ho Chi Minh, Busan, Yokohama, Kaohsiung e Jacarta.
- Veículos elétricos = NCM 8703.80.00. Painéis solares = NCM 8541.43.00.

REGRAS
- Valores monetários em dólares (US$) salvo pedido explícito em reais (use valor_fob_brl). Use abreviações (mi, bi) em textos.
- Para rankings, ordene de forma decrescente e retorne o TOP 10 se o usuário não especificar.
- "Este ano" = 2026; os dados vão de jan/2024 a set/2026. "Hoje" nos dados = 30/09/2026.
- Para análises mensais agregadas prefira as tabelas gold_*; para detalhes por DI, importador ou NCM use silver_importacoes.
- Empresas: junte por cnpj_importador / cnpj_exportador / consignatario_cnpj = silver_empresas.cnpj.
- Os dados são sintéticos (workshop) — não invente informações que não estejam nas tabelas."""

EXEMPLOS = [
    ("Qual o saldo da balança comercial por mês em 2026?",
     f"SELECT mes, SUM(IF(fluxo = 'Exportação', valor_fob_usd, 0)) AS fob_exportado_usd, "
     f"SUM(IF(fluxo = 'Importação', valor_fob_usd, 0)) AS fob_importado_usd, "
     f"SUM(IF(fluxo = 'Exportação', valor_fob_usd, -valor_fob_usd)) AS saldo_usd "
     f"FROM {T}.gold_comercio_exterior_mensal WHERE year(mes) = 2026 GROUP BY mes ORDER BY mes"),
    ("Quais os 10 maiores importadores de veículos elétricos em 2026?",
     f"SELECT razao_social_importador, uf_importador, COUNT(*) AS qtd_dis, SUM(valor_fob_usd) AS valor_fob_usd "
     f"FROM {T}.silver_importacoes WHERE ncm = '8703.80.00' AND year(data_registro) = 2026 "
     f"GROUP BY ALL ORDER BY valor_fob_usd DESC LIMIT 10"),
    ("Qual o tempo médio de desembaraço por porto marítimo, mês a mês, em 2026?",
     f"SELECT mes, porto, ROUND(SUM(tempo_medio_desembaraco_dias * qtd_dis) / SUM(qtd_dis), 1) AS dias_medios "
     f"FROM {T}.gold_desempenho_portos WHERE via_transporte = 'Marítima' AND year(mes) = 2026 "
     f"GROUP BY ALL ORDER BY mes, porto"),
]
PERGUNTAS = [
    "Qual foi o valor FOB importado em 2025 por categoria de NCM?",
    "Quais os 10 maiores importadores de veículos elétricos em 2026?",
    "Como evoluiu o tempo médio de desembaraço no Porto de Paranaguá em 2026?",
    "Qual armador tem o maior atraso médio nas rotas vindas da Ásia?",
    "Quantos contêineres estão em trânsito atrasados, por porto de destino?",
    "Qual o saldo da balança comercial por mês em 2026?",
]
BENCHMARKS = [
    ("Qual o valor FOB total importado em 2025?",
     f"SELECT SUM(valor_fob_usd) AS fob_importado_usd FROM {T}.silver_importacoes WHERE year(data_registro) = 2025"),
    ("Qual o percentual de DIs em canal vermelho no Porto de Paranaguá desde junho de 2026?",
     f"SELECT ROUND(100 * AVG(IF(canal_parametrizacao = 'Vermelho', 1, 0)), 1) AS pct_vermelho FROM {T}.silver_importacoes "
     f"WHERE urf_despacho = 'Porto de Paranaguá' AND data_registro >= '2026-06-01'"),
    ("Qual armador tem o maior atraso médio?",
     f"SELECT armador, ROUND(AVG(atraso_dias), 1) AS atraso_medio_dias FROM {T}.gold_embarques GROUP BY armador ORDER BY atraso_medio_dias DESC LIMIT 1"),
]


def ids(n):
    return sorted(uuid4().hex for _ in range(n))


espaco = {
    "version": 2,
    "config": {"sample_questions": [{"id": i, "question": [q]} for i, q in zip(ids(len(PERGUNTAS)), PERGUNTAS)]},
    "data_sources": {"tables": [{"identifier": f"{T}.{t}"} for t in sorted(TABELAS)]},
    "instructions": {
        "text_instructions": [{"id": uuid4().hex, "content": [INSTRUCOES]}],
        "example_question_sqls": [{"id": i, "question": [q], "sql": [s]} for i, (q, s) in zip(ids(len(EXEMPLOS)), EXEMPLOS)],
    },
    "benchmarks": {"questions": [{"id": i, "question": [q], "answer": [{"format": "SQL", "content": [s]}]}
                                 for i, (q, s) in zip(ids(len(BENCHMARKS)), BENCHMARKS)]},
}
corpo = {"title": f"Radar Comex — LogComex Workshop ({SLUG})",
         "description": "Pergunte em português sobre importações, exportações, desembaraço aduaneiro e rastreamento de contêineres (dados sintéticos).",
         "warehouse_id": WAREHOUSE_ID, "serialized_space": json.dumps(espaco, ensure_ascii=False)}

w.workspace.mkdirs(PASTA_USUARIO)
space_id = cfg_get("genie_space_id")
try:
    if not space_id:
        raise LookupError
    api("PATCH", f"/api/2.0/genie/spaces/{space_id}", corpo)
except Exception:
    space_id = api("POST", "/api/2.0/genie/spaces", {**corpo, "parent_path": PASTA_USUARIO})["space_id"]
    cfg_set("genie_space_id", space_id)

URL_GENIE = url_workspace(f"/genie/rooms/{space_id}")
displayHTML(f"""<div style="font-family:Poppins,Arial;background:{PRETO};color:white;padding:18px 24px;border-radius:12px;border-left:8px solid {ROXO}">
<div style="font-size:20px;font-weight:700">🧞 Genie space criado!</div>
<div style="margin-top:8px"><a style="color:{ROXO_CLARO};font-weight:700" href="{URL_GENIE}" target="_blank">➜ Abrir o Genie Radar Comex</a></div></div>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💬 Exercícios
# MAGIC
# MAGIC ### 1. Primeiras perguntas (8 min)
# MAGIC Abra o Genie (link acima) e clique numa das **perguntas sugeridas**, depois experimente perguntas livres:
# MAGIC - *"Quais países mais exportam painéis solares para o Brasil e qual o preço médio por kg?"*
# MAGIC - *"Compare o tempo de desembaraço de Paranaguá com Santos nos últimos 6 meses"* → peça em seguida **"mostre em um gráfico de linhas"**.
# MAGIC - *"Por que o tempo de desembaraço em Paranaguá aumentou?"* (veja como ele investiga os canais de parametrização)
# MAGIC
# MAGIC Em cada resposta, clique em **Show code** para ver o SQL gerado. Use 👍 / 👎 para dar feedback.
# MAGIC
# MAGIC ### 2. Ensinando um conceito de negócio (10 min)
# MAGIC Pergunte: *"Quantas operações críticas tivemos em 2026?"* — o Genie não sabe o que é isso (ou vai chutar).
# MAGIC
# MAGIC 1. Clique em **Configure → Instructions** (ou **Instructions** no menu do espaço) e adicione no texto geral:
# MAGIC    > *Operação crítica = DI em canal Vermelho ou Cinza com valor FOB acima de US$ 1 milhão.*
# MAGIC 2. Faça a mesma pergunta de novo. ✅
# MAGIC 3. Vá em **SQL Expressions** (ou *Knowledge / SQL snippets*) e crie uma **medida** reutilizável, por exemplo:
# MAGIC    - Nome: `ticket_medio_fob` · Expressão: `SUM(valor_fob_usd) / COUNT(DISTINCT numero_di)` · Tabela: `silver_importacoes`
# MAGIC    e pergunte *"qual o ticket médio FOB por categoria em 2026?"*.
# MAGIC
# MAGIC ### 3. Avaliação com Benchmarks (5 min)
# MAGIC Abra a aba **Benchmarks** → **Run all benchmarks**. O Genie compara as respostas com o SQL "gabarito".
# MAGIC Adicione uma nova pergunta de benchmark a partir de uma resposta que você aprovou.
# MAGIC
# MAGIC ### 4. Leve o Genie para onde o usuário está (5 min)
# MAGIC - No **dashboard do Lab 2**, em modo edição → **Settings** → habilite o **Genie** e vincule este espaço: os usuários
# MAGIC   fazem perguntas sem sair do painel.
# MAGIC - **Share** o espaço com um colega (permissão *Can run*) — ele verá apenas os dados que o Unity Catalog permitir.
# MAGIC - No **Lab 4**, o nosso app vai conversar com este mesmo espaço via **Genie Conversation API**. 🚀
