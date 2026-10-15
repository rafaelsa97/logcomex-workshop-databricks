# Databricks notebook source
# MAGIC %md
# MAGIC # 🟣 Lab 1 — Engenharia de dados no Databricks (Arquitetura Medalhão)
# MAGIC
# MAGIC **Tempo estimado:** 30 minutos
# MAGIC
# MAGIC Vamos transformar os arquivos brutos do comércio exterior em tabelas confiáveis e prontas para BI e IA:
# MAGIC
# MAGIC ```
# MAGIC  Arquivos (Volume)        🥉 BRONZE                 🥈 SILVER                        🥇 GOLD
# MAGIC  ─────────────────        ─────────────            ────────────────────           ─────────────────────────
# MAGIC  importacoes/*.csv  ──▶   bronze_importacoes  ──▶  silver_importacoes       ──▶  gold_comercio_exterior_mensal
# MAGIC  exportacoes/*.csv  ──▶   bronze_exportacoes  ──▶  silver_exportacoes       ──▶  gold_desempenho_portos
# MAGIC  eventos/*.json     ──▶   bronze_eventos      ──▶  silver_eventos_embarque  ──▶  gold_embarques
# MAGIC  referencias/*.csv  ──▶   bronze_empresas/ncm/cambio ──▶ silver_empresas / silver_ncm / silver_cambio_diario
# MAGIC ```
# MAGIC
# MAGIC | Conceito | O que você vai ver |
# MAGIC |---|---|
# MAGIC | **Unity Catalog** | catálogo → schema → tabelas/volumes, com governança e linhagem automáticas |
# MAGIC | **Auto Loader** | ingestão **incremental** de arquivos (só processa o que é novo) |
# MAGIC | **`read_files`** | leitura de CSV/JSON direto em SQL, com inferência de schema |
# MAGIC | **Delta Lake** | transações ACID, *constraints*, histórico e *time travel* |
# MAGIC | **SQL** | limpeza, deduplicação, enriquecimento e agregações |
# MAGIC
# MAGIC > ▶️ Conecte ao compute **Serverless** e execute as células **uma a uma** (Shift + Enter), lendo as explicações.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

dbutils.widgets.dropdown("modo", "interativo", ["interativo", "automatico"], "Modo")
spark.sql(f"USE CATALOG `{CATALOGO}`")
spark.sql(f"USE SCHEMA `{SCHEMA}`")
resumo()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.1 Explorando a *landing zone*
# MAGIC
# MAGIC Os arquivos brutos estão num **Volume** do Unity Catalog — um local governado para arquivos (CSV, JSON, PDFs, imagens...).
# MAGIC Você também pode navegá-lo pela interface: **Catalog → seu catálogo → seu schema → Volumes → landing**.

# COMMAND ----------

display(dbutils.fs.ls(f"{LANDING}/importacoes"))

# COMMAND ----------

# MAGIC %md
# MAGIC Com `read_files` lemos o arquivo direto em SQL, sem criar tabela. Repare que o schema é inferido automaticamente.

# COMMAND ----------

display(spark.sql(f"""
  SELECT * FROM read_files('{LANDING}/importacoes/importacoes_2026_08.csv', format => 'csv', header => true)
  LIMIT 10
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.2 🥉 Bronze — ingestão incremental com Auto Loader
# MAGIC
# MAGIC Novos arquivos de DIs chegam todo mês. O **Auto Loader** (`cloudFiles`) guarda em um *checkpoint* quais arquivos
# MAGIC já foram processados — a cada execução, **só os arquivos novos são lidos**. Ideal para ingestões contínuas de
# MAGIC sistemas como Siscomex, APIs de armadores ou SFTPs de clientes.
# MAGIC
# MAGIC Na Bronze mantemos o dado **como chegou** (tudo como texto) + metadados de auditoria (arquivo de origem e horário).

# COMMAND ----------

from pyspark.sql import functions as F


def ingerir_importacoes():
    """Ingestão incremental das DIs (CSV) para a tabela bronze_importacoes."""
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINTS}/bronze_importacoes/schema")
        .load(f"{LANDING}/importacoes")
        .withColumn("_arquivo_origem", F.col("_metadata.file_name"))
        .withColumn("_ingestao_ts", F.current_timestamp())
        .writeStream
        .option("checkpointLocation", f"{CHECKPOINTS}/bronze_importacoes")
        .trigger(availableNow=True)          # processa o que há de novo e encerra (modo "batch incremental")
        .toTable("bronze_importacoes")
        .awaitTermination())
    return spark.table("bronze_importacoes").count()


print(f"Linhas em bronze_importacoes: {ingerir_importacoes():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC As demais fontes são carregadas com SQL usando `read_files` — inclusive o **JSON aninhado** dos eventos de rastreamento.

# COMMAND ----------

fontes = {
    "bronze_exportacoes": ("exportacoes", "csv"),
    "bronze_eventos_embarque": ("eventos_embarque", "json"),
    "bronze_empresas": ("referencias/empresas.csv", "csv"),
    "bronze_ncm": ("referencias/ncm.csv", "csv"),
    "bronze_cambio": ("referencias/cambio_ptax.csv", "csv"),
}
for tabela, (caminho, formato) in fontes.items():
    opcoes = ", header => true, inferSchema => false" if formato == "csv" else ""
    spark.sql(f"""
        CREATE OR REPLACE TABLE {tabela} AS
        SELECT *, _metadata.file_name AS _arquivo_origem, current_timestamp() AS _ingestao_ts
        FROM read_files('{LANDING}/{caminho}', format => '{formato}'{opcoes})
    """)
    print(f"{tabela:<26} {spark.table(tabela).count():>8,} linhas")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Os eventos chegam como JSON aninhado: repare nas colunas do tipo STRUCT (navio, rota, evento)
# MAGIC SELECT container, armador, navio, rota, evento FROM bronze_eventos_embarque LIMIT 5

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.3 📬 Chegou um arquivo novo!
# MAGIC
# MAGIC O arquivo de **setembro/2026** acabou de chegar na landing zone. Rode a ingestão de novo e observe:
# MAGIC o Auto Loader processa **apenas o arquivo novo** — nada é reprocessado.

# COMMAND ----------

origem, destino = f"{LANDING}/_chegando/importacoes_2026_09.csv", f"{LANDING}/importacoes/importacoes_2026_09.csv"
if os.path.exists(origem):
    dbutils.fs.mv(origem, destino)
    print("📬 Arquivo importacoes_2026_09.csv chegou na landing zone!")

antes = spark.table("bronze_importacoes").count()
depois = ingerir_importacoes()
print(f"Antes: {antes:,} | Depois: {depois:,} | Novas linhas: {depois - antes:,}")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Quais arquivos foram ingeridos e quando? (auditoria via colunas de metadados)
# MAGIC SELECT _arquivo_origem, count(*) AS linhas, min(_ingestao_ts) AS ingerido_em
# MAGIC FROM bronze_importacoes GROUP BY ALL ORDER BY _arquivo_origem DESC LIMIT 5

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.4 🥈 Silver — limpeza, padronização e enriquecimento
# MAGIC
# MAGIC Antes de limpar, vamos **medir** os problemas de qualidade dos dados brutos:

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   count(*)                                             AS total_linhas,
# MAGIC   count(*) - count(DISTINCT numero_di)                 AS dis_duplicadas,
# MAGIC   count_if(CAST(valor_fob_usd AS DOUBLE) <= 0)         AS valor_fob_invalido,
# MAGIC   count_if(ncm IS NULL OR trim(ncm) = '')              AS ncm_ausente,
# MAGIC   count(DISTINCT pais_origem)                          AS grafias_de_paises,
# MAGIC   count(DISTINCT initcap(trim(pais_origem)))           AS paises_reais
# MAGIC FROM bronze_importacoes

# COMMAND ----------

# MAGIC %md
# MAGIC Primeiro as **dimensões** (empresas, NCM e câmbio). Para o câmbio criamos um calendário diário que repete a última
# MAGIC PTAX disponível em fins de semana e feriados (*forward fill*).

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_empresas
# MAGIC COMMENT 'Cadastro de empresas importadoras e exportadoras (dados sintéticos)' AS
# MAGIC SELECT cnpj, razao_social, uf, setor, porte, perfil, to_date(data_cadastro) AS data_cadastro
# MAGIC FROM bronze_empresas;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE silver_ncm
# MAGIC COMMENT 'Tabela de referência da Nomenclatura Comum do Mercosul (NCM) usada no workshop' AS
# MAGIC SELECT codigo_ncm, descricao, categoria, capitulo, fluxo_predominante,
# MAGIC        CAST(nullif(aliquota_ii, '') AS DOUBLE) AS aliquota_ii
# MAGIC FROM bronze_ncm;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE silver_cambio_diario
# MAGIC COMMENT 'Taxa PTAX de venda USD/BRL por dia corrido (fins de semana repetem a última cotação)' AS
# MAGIC WITH calendario AS (
# MAGIC   SELECT explode(sequence(DATE'2024-01-01', DATE'2026-12-31', INTERVAL 1 DAY)) AS data
# MAGIC ), ptax AS (
# MAGIC   SELECT to_date(data) AS data, CAST(taxa_venda AS DOUBLE) AS ptax_venda FROM bronze_cambio
# MAGIC )
# MAGIC SELECT c.data,
# MAGIC        last_value(p.ptax_venda, true) OVER (ORDER BY c.data ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ptax_venda
# MAGIC FROM calendario c LEFT JOIN ptax p USING (data);

# COMMAND ----------

# MAGIC %md
# MAGIC Agora a tabela principal: **DIs de importação**. Num único `SELECT` fazemos:
# MAGIC - **tipagem** (texto → data / decimal), **padronização** de países (`CHINA `, `china` → `China`);
# MAGIC - **deduplicação** de DIs reenviadas com `QUALIFY ROW_NUMBER()`;
# MAGIC - **enriquecimento** com NCM, importador e câmbio do dia; cálculo de CIF, valor em R$, preço médio/kg e tempo de desembaraço;
# MAGIC - registros inválidos vão para uma tabela de **quarentena** (`silver_importacoes_rejeitadas`) em vez de sumirem.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TEMPORARY VIEW v_importacoes_tipadas AS
# MAGIC SELECT
# MAGIC   trim(numero_di)                                         AS numero_di,
# MAGIC   to_date(data_registro)                                  AS data_registro,
# MAGIC   trim(cnpj_importador)                                   AS cnpj_importador,
# MAGIC   nullif(trim(ncm), '')                                   AS ncm,
# MAGIC   regexp_replace(regexp_replace(initcap(trim(pais_origem)), ' Do ', ' do '), ' E ', ' e ') AS pais_origem,
# MAGIC   urf_despacho, via_transporte, incoterm,
# MAGIC   CAST(valor_fob_usd AS DECIMAL(18,2))                    AS valor_fob_usd,
# MAGIC   CAST(frete_usd AS DECIMAL(18,2))                        AS frete_usd,
# MAGIC   CAST(seguro_usd AS DECIMAL(18,2))                       AS seguro_usd,
# MAGIC   CAST(peso_liquido_kg AS DOUBLE)                         AS peso_liquido_kg,
# MAGIC   canal_parametrizacao,
# MAGIC   to_date(nullif(data_desembaraco, ''))                   AS data_desembaraco,
# MAGIC   nullif(armador, '')                                     AS armador,
# MAGIC   CAST(qtd_containers AS INT)                             AS qtd_containers,
# MAGIC   _arquivo_origem, _ingestao_ts
# MAGIC FROM bronze_importacoes
# MAGIC QUALIFY ROW_NUMBER() OVER (PARTITION BY trim(numero_di) ORDER BY _ingestao_ts DESC) = 1;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE silver_importacoes_rejeitadas
# MAGIC COMMENT 'Quarentena: DIs com problemas de qualidade (valor FOB inválido ou NCM ausente)' AS
# MAGIC SELECT *, CASE WHEN ncm IS NULL THEN 'NCM ausente' ELSE 'Valor FOB inválido' END AS motivo_rejeicao
# MAGIC FROM v_importacoes_tipadas
# MAGIC WHERE ncm IS NULL OR valor_fob_usd IS NULL OR valor_fob_usd <= 0;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE silver_importacoes
# MAGIC COMMENT 'DIs (Declarações de Importação) limpas, deduplicadas e enriquecidas com NCM, importador e câmbio PTAX. Uma linha por DI.' AS
# MAGIC SELECT
# MAGIC   i.numero_di, i.data_registro,
# MAGIC   CAST(date_trunc('MONTH', i.data_registro) AS DATE)     AS mes_registro,
# MAGIC   i.cnpj_importador, e.razao_social AS razao_social_importador, e.uf AS uf_importador,
# MAGIC   e.setor AS setor_importador, e.porte AS porte_importador,
# MAGIC   i.ncm, n.descricao AS descricao_ncm, n.categoria AS categoria_ncm,
# MAGIC   i.pais_origem, i.urf_despacho, i.via_transporte, i.incoterm,
# MAGIC   i.valor_fob_usd, i.frete_usd, i.seguro_usd,
# MAGIC   i.valor_fob_usd + i.frete_usd + i.seguro_usd                                AS valor_cif_usd,
# MAGIC   c.ptax_venda,
# MAGIC   CAST(i.valor_fob_usd * c.ptax_venda AS DECIMAL(18,2))                       AS valor_fob_brl,
# MAGIC   CAST((i.valor_fob_usd + i.frete_usd + i.seguro_usd) * n.aliquota_ii AS DECIMAL(18,2)) AS ii_estimado_usd,
# MAGIC   i.peso_liquido_kg,
# MAGIC   round(i.valor_fob_usd / i.peso_liquido_kg, 4)                               AS preco_medio_usd_kg,
# MAGIC   i.canal_parametrizacao, i.data_desembaraco,
# MAGIC   datediff(i.data_desembaraco, i.data_registro)                                AS dias_desembaraco,
# MAGIC   IF(i.data_desembaraco IS NULL, 'Em análise', 'Desembaraçada')                AS status_desembaraco,
# MAGIC   i.armador, i.qtd_containers, i._arquivo_origem
# MAGIC FROM v_importacoes_tipadas i
# MAGIC JOIN silver_ncm n            ON i.ncm = n.codigo_ncm
# MAGIC LEFT JOIN silver_empresas e  ON i.cnpj_importador = e.cnpj
# MAGIC LEFT JOIN silver_cambio_diario c ON i.data_registro = c.data
# MAGIC WHERE i.valor_fob_usd > 0;
# MAGIC
# MAGIC -- Regra de qualidade garantida pelo Delta Lake: qualquer escrita futura que viole a regra é bloqueada
# MAGIC ALTER TABLE silver_importacoes ADD CONSTRAINT valor_fob_positivo CHECK (valor_fob_usd > 0);
# MAGIC
# MAGIC SELECT (SELECT count(*) FROM silver_importacoes) AS dis_validas,
# MAGIC        (SELECT count(*) FROM silver_importacoes_rejeitadas) AS dis_em_quarentena,
# MAGIC        (SELECT count(DISTINCT pais_origem) FROM silver_importacoes) AS paises_padronizados;

# COMMAND ----------

# MAGIC %md
# MAGIC 🧪 **Teste a constraint**: tente inserir uma DI com valor negativo. O Delta Lake vai **rejeitar** a escrita
# MAGIC (o erro abaixo é esperado!).

# COMMAND ----------

try:
    spark.sql("INSERT INTO silver_importacoes (numero_di, valor_fob_usd) VALUES ('TESTE', -100)")
except Exception as erro:
    print("🛡️ Escrita bloqueada pela constraint:", str(erro).split("\n")[0][:160])

# COMMAND ----------

# MAGIC %md
# MAGIC Exportações (DU-E) e eventos de rastreamento seguem o mesmo padrão. Nos eventos, "achatamos" o JSON aninhado
# MAGIC com a notação `coluna.campo`.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_exportacoes
# MAGIC COMMENT 'DU-Es (Declarações Únicas de Exportação) limpas, deduplicadas e enriquecidas. Uma linha por DU-E.' AS
# MAGIC SELECT
# MAGIC   x.numero_due, to_date(x.data_embarque) AS data_embarque,
# MAGIC   CAST(date_trunc('MONTH', to_date(x.data_embarque)) AS DATE) AS mes_embarque,
# MAGIC   x.cnpj_exportador, e.razao_social AS razao_social_exportador, e.setor AS setor_exportador,
# MAGIC   x.uf_produtor, x.ncm, n.descricao AS descricao_ncm, n.categoria AS categoria_ncm,
# MAGIC   x.pais_destino, x.porto_embarque, x.via_transporte,
# MAGIC   CAST(x.valor_fob_usd AS DECIMAL(18,2)) AS valor_fob_usd,
# MAGIC   CAST(x.valor_fob_usd * c.ptax_venda AS DECIMAL(18,2)) AS valor_fob_brl,
# MAGIC   CAST(x.peso_liquido_kg AS DOUBLE) AS peso_liquido_kg
# MAGIC FROM bronze_exportacoes x
# MAGIC JOIN silver_ncm n ON x.ncm = n.codigo_ncm
# MAGIC LEFT JOIN silver_empresas e ON x.cnpj_exportador = e.cnpj
# MAGIC LEFT JOIN silver_cambio_diario c ON to_date(x.data_embarque) = c.data
# MAGIC QUALIFY ROW_NUMBER() OVER (PARTITION BY x.numero_due ORDER BY x._ingestao_ts DESC) = 1;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE silver_eventos_embarque
# MAGIC COMMENT 'Eventos de rastreamento de contêineres (milestones dos armadores), deduplicados. Uma linha por evento.' AS
# MAGIC SELECT
# MAGIC   id_evento, container, bl, armador,
# MAGIC   navio.nome                         AS navio,
# MAGIC   consignatario_cnpj,
# MAGIC   rota.porto_origem                  AS porto_origem,
# MAGIC   rota.porto_destino                 AS porto_destino,
# MAGIC   to_timestamp(rota.eta_prevista)    AS eta_prevista,
# MAGIC   evento.codigo                      AS codigo_evento,
# MAGIC   evento.descricao                   AS descricao_evento,
# MAGIC   evento.local                       AS local_evento,
# MAGIC   to_timestamp(evento.data_hora)     AS data_hora_evento
# MAGIC FROM bronze_eventos_embarque
# MAGIC QUALIFY ROW_NUMBER() OVER (PARTITION BY id_evento ORDER BY _ingestao_ts DESC) = 1;
# MAGIC
# MAGIC SELECT * FROM silver_eventos_embarque WHERE container = (SELECT max(container) FROM silver_eventos_embarque) ORDER BY data_hora_evento;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.5 🥇 Gold — tabelas de negócio prontas para consumo
# MAGIC
# MAGIC A camada Gold responde perguntas de negócio. Serão a base do **Dashboard (Lab 2)**, do **Genie (Lab 3)** e do **App (Lab 4)**.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Balança comercial mensal: importação + exportação no mesmo formato
# MAGIC CREATE OR REPLACE TABLE gold_comercio_exterior_mensal
# MAGIC COMMENT 'Visão mensal do comércio exterior (importação e exportação) por NCM, país parceiro, UF, porto e via de transporte.' AS
# MAGIC SELECT mes_registro AS mes, 'Importação' AS fluxo, ncm, descricao_ncm, categoria_ncm,
# MAGIC        pais_origem AS pais_parceiro, uf_importador AS uf, urf_despacho AS porto, via_transporte,
# MAGIC        count(*) AS qtd_operacoes, sum(valor_fob_usd) AS valor_fob_usd, sum(valor_fob_brl) AS valor_fob_brl,
# MAGIC        round(sum(peso_liquido_kg) / 1000, 1) AS toneladas
# MAGIC FROM silver_importacoes GROUP BY ALL
# MAGIC UNION ALL
# MAGIC SELECT mes_embarque, 'Exportação', ncm, descricao_ncm, categoria_ncm,
# MAGIC        pais_destino, uf_produtor, porto_embarque, via_transporte,
# MAGIC        count(*), sum(valor_fob_usd), sum(valor_fob_brl), round(sum(peso_liquido_kg) / 1000, 1)
# MAGIC FROM silver_exportacoes GROUP BY ALL;
# MAGIC
# MAGIC -- Eficiência aduaneira por porto/aeroporto/fronteira
# MAGIC CREATE OR REPLACE TABLE gold_desempenho_portos
# MAGIC COMMENT 'Desempenho do desembaraço aduaneiro de importação por mês e local de despacho (URF): volume, canais de parametrização e tempo de desembaraço.' AS
# MAGIC SELECT mes_registro AS mes, urf_despacho AS porto, via_transporte,
# MAGIC        count(*)                                        AS qtd_dis,
# MAGIC        count_if(canal_parametrizacao = 'Verde')        AS qtd_canal_verde,
# MAGIC        count_if(canal_parametrizacao = 'Amarelo')      AS qtd_canal_amarelo,
# MAGIC        count_if(canal_parametrizacao = 'Vermelho')     AS qtd_canal_vermelho,
# MAGIC        count_if(canal_parametrizacao = 'Cinza')        AS qtd_canal_cinza,
# MAGIC        round(avg(dias_desembaraco), 2)                 AS tempo_medio_desembaraco_dias,
# MAGIC        percentile_approx(dias_desembaraco, 0.9)        AS p90_desembaraco_dias,
# MAGIC        sum(valor_fob_usd)                              AS valor_fob_usd
# MAGIC FROM silver_importacoes GROUP BY ALL;
# MAGIC
# MAGIC -- Uma linha por contêiner: situação atual, transit time e atraso vs. ETA
# MAGIC CREATE OR REPLACE TABLE gold_embarques
# MAGIC COMMENT 'Situação de cada contêiner rastreado: rota, armador, datas de partida/chegada, transit time e atraso em relação à ETA prevista.' AS
# MAGIC WITH ref AS (SELECT max(data_hora_evento) AS agora FROM silver_eventos_embarque),
# MAGIC por_container AS (
# MAGIC   SELECT container, bl, armador, navio, consignatario_cnpj, porto_origem, porto_destino,
# MAGIC          min(eta_prevista)                                              AS eta_prevista,
# MAGIC          min(IF(codigo_evento = 'PARTIDA', data_hora_evento, NULL))     AS data_partida,
# MAGIC          min(IF(codigo_evento = 'CHEGADA', data_hora_evento, NULL))     AS data_chegada,
# MAGIC          max_by(codigo_evento, data_hora_evento)                        AS ultimo_evento,
# MAGIC          max(data_hora_evento)                                          AS data_ultimo_evento,
# MAGIC          bool_or(codigo_evento = 'TRANSBORDO')                          AS teve_transbordo
# MAGIC   FROM silver_eventos_embarque GROUP BY ALL
# MAGIC )
# MAGIC SELECT p.*, e.razao_social AS consignatario,
# MAGIC        round((unix_timestamp(p.data_chegada) - unix_timestamp(p.data_partida)) / 86400, 1) AS transit_time_dias,
# MAGIC        round(greatest(0, (unix_timestamp(coalesce(p.data_chegada, r.agora)) - unix_timestamp(p.eta_prevista)) / 86400), 1) AS atraso_dias,
# MAGIC        CASE WHEN p.ultimo_evento = 'GATE_OUT' THEN 'Entregue'
# MAGIC             WHEN p.data_chegada IS NOT NULL THEN 'No porto de destino'
# MAGIC             WHEN p.eta_prevista < r.agora THEN 'Em trânsito - atrasado'
# MAGIC             ELSE 'Em trânsito' END AS status_embarque
# MAGIC FROM por_container p CROSS JOIN ref r
# MAGIC LEFT JOIN silver_empresas e ON p.consignatario_cnpj = e.cnpj
# MAGIC WHERE p.data_partida IS NOT NULL;
# MAGIC
# MAGIC SELECT status_embarque, count(*) AS conteineres, round(avg(atraso_dias), 1) AS atraso_medio_dias
# MAGIC FROM gold_embarques GROUP BY ALL ORDER BY conteineres DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC 🔎 **Primeira descoberta:** qual porto teve o maior aumento no tempo de desembaraço nos últimos meses?

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT porto,
# MAGIC        round(avg(IF(mes <  '2026-06-01', tempo_medio_desembaraco_dias, NULL)), 1) AS dias_antes_jun26,
# MAGIC        round(avg(IF(mes >= '2026-06-01', tempo_medio_desembaraco_dias, NULL)), 1) AS dias_desde_jun26
# MAGIC FROM gold_desempenho_portos
# MAGIC WHERE via_transporte = 'Marítima'
# MAGIC GROUP BY porto ORDER BY dias_desde_jun26 - dias_antes_jun26 DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.6 🛡️ Governança: documentação, histórico e linhagem
# MAGIC
# MAGIC **Documentar colunas** é o que torna o Genie (Lab 3) preciso: ele usa esses comentários para entender o negócio.
# MAGIC A célula abaixo documenta as principais colunas. *(Dica: no Catalog Explorer, o botão **AI generate** sugere
# MAGIC descrições automaticamente!)*

# COMMAND ----------

COMENTARIOS = {
    "silver_importacoes": {
        "numero_di": "Número da Declaração de Importação (DI/DUIMP) no Siscomex",
        "data_registro": "Data de registro da DI",
        "valor_fob_usd": "Valor FOB da mercadoria em dólares (sem frete e seguro)",
        "valor_cif_usd": "Valor CIF em dólares = FOB + frete internacional + seguro",
        "valor_fob_brl": "Valor FOB convertido para reais pela PTAX de venda do dia",
        "ii_estimado_usd": "Imposto de Importação estimado (CIF x alíquota do II da NCM)",
        "canal_parametrizacao": "Canal de conferência aduaneira: Verde (liberação automática), Amarelo (documental), Vermelho (documental + física), Cinza (valoração aduaneira)",
        "dias_desembaraco": "Dias corridos entre o registro e o desembaraço da DI (lead time aduaneiro)",
        "status_desembaraco": "Desembaraçada ou Em análise (ainda sem desembaraço)",
        "urf_despacho": "Unidade da Receita Federal de despacho: porto, aeroporto ou fronteira",
        "preco_medio_usd_kg": "Preço médio da mercadoria em USD por kg (FOB / peso líquido)",
    },
    "gold_embarques": {
        "transit_time_dias": "Dias entre a partida do porto de origem e a chegada no porto de destino",
        "atraso_dias": "Dias de atraso da chegada (real ou ainda pendente) em relação à ETA prevista; 0 = no prazo",
        "status_embarque": "Entregue, No porto de destino, Em trânsito ou Em trânsito - atrasado",
        "eta_prevista": "Data/hora estimada de chegada informada pelo armador",
    },
    "gold_comercio_exterior_mensal": {
        "fluxo": "Importação ou Exportação",
        "pais_parceiro": "País de origem (importação) ou de destino (exportação)",
        "valor_fob_usd": "Soma do valor FOB em dólares",
        "toneladas": "Peso líquido total em toneladas",
    },
}
for tabela, colunas in COMENTARIOS.items():
    for coluna, texto in colunas.items():
        spark.sql(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} COMMENT '{texto}'")
print("📝 Colunas documentadas.")
try:  # tags facilitam busca e classificação (alguns workspaces restringem chaves/valores via tag policies)
    spark.sql("ALTER TABLE silver_importacoes SET TAGS ('workshop' = 'logcomex', 'camada' = 'silver', 'contem_cnpj' = 'sim')")
    print("🏷️ Tags aplicadas em silver_importacoes.")
except Exception as erro:
    print("🏷️ Tags não aplicadas (política de tags do workspace):", str(erro).splitlines()[0][:150])

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Todo comando fica registrado no histórico da tabela Delta
# MAGIC DESCRIBE HISTORY silver_importacoes

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Time travel: consulte a tabela como ela era na versão 0
# MAGIC SELECT count(*) AS linhas_na_versao_0 FROM silver_importacoes VERSION AS OF 0

# COMMAND ----------

# MAGIC %md
# MAGIC ### 👀 Veja a linhagem
# MAGIC 1. No menu lateral, abra **Catalog** → seu catálogo → schema `logcomex_ws_<seu_usuario>` → tabela **gold_embarques**.
# MAGIC 2. Clique na aba **Lineage** → **See lineage graph**: o Unity Catalog mostra, sem nenhuma configuração,
# MAGIC    o caminho `arquivos → bronze → silver → gold` (e, mais tarde, o dashboard e o Genie que usam a tabela).
# MAGIC
# MAGIC ### 🏁 Desafio (opcional, se sobrar tempo)
# MAGIC - Clique em **Schedule** (canto superior direito) para transformar este notebook em um **Lakeflow Job** diário.
# MAGIC - Pergunte ao **Databricks Assistant** (ícone ✨): *"crie uma tabela gold com o ranking dos 20 maiores importadores por valor FOB em 2026"*.

# COMMAND ----------

if dbutils.widgets.get("modo") == "automatico":
    dbutils.notebook.exit("Lab 1 executado automaticamente com sucesso")
print("✅ Lab 1 concluído! Próximo: 02_Dashboard_AIBI")
