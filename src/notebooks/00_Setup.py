# Databricks notebook source
# MAGIC %md
# MAGIC # 🟣 Workshop LogComex × Databricks — Lab 0: Setup automatizado
# MAGIC
# MAGIC **Tempo estimado:** 10 minutos (a execução leva ~3 min).
# MAGIC
# MAGIC Este notebook prepara **todo o seu ambiente** do workshop, sem nenhum passo manual:
# MAGIC
# MAGIC | # | O que é criado | Onde |
# MAGIC |---|---|---|
# MAGIC | 1 | Schema isolado para você | `<catálogo>.logcomex_ws_<seu_usuario>` |
# MAGIC | 2 | Volume com a *landing zone* de arquivos brutos (CSV + JSON) | `/Volumes/<catálogo>/<schema>/landing` |
# MAGIC | 3 | **Dados sintéticos de comércio exterior** (DIs de importação, DU-Es de exportação, eventos de rastreamento de contêineres, empresas, NCM, câmbio PTAX) | arquivos no volume |
# MAGIC | 4 | Seleção (ou criação) de um **SQL Warehouse** serverless | usado por Dashboard, Genie e App |
# MAGIC | 5 | Criação antecipada do **Databricks App** (o compute leva alguns minutos para subir) | Compute → Apps |
# MAGIC
# MAGIC ### ▶️ Como executar
# MAGIC 1. No canto superior direito, conecte o notebook ao compute **Serverless**.
# MAGIC 2. Clique em **Run all** (Executar tudo).
# MAGIC 3. Aguarde a mensagem final **✅ Setup concluído**.
# MAGIC
# MAGIC > 💡 Todos os dados são **100% sintéticos**, gerados para refletir a realidade do comércio exterior
# MAGIC > brasileiro (NCMs reais, portos, armadores, canais de parametrização), mas sem nenhum dado real de empresas.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Schema e volume

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ} COMMENT 'Workshop LogComex x Databricks — ambiente de {USUARIO}'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.`{VOLUME}` COMMENT 'Landing zone de arquivos brutos (CSV/JSON) do workshop'")
spark.sql(f"USE {FQ}")
resumo()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Geração dos dados sintéticos de comércio exterior
# MAGIC
# MAGIC Cenário simulado (jan/2024 → set/2026):
# MAGIC - **~47 mil DIs** de importação de 260 importadores brasileiros, com 24 NCMs reais (painéis solares, veículos elétricos, fertilizantes, eletrônicos, fármacos...).
# MAGIC - **~20 mil DU-Es** de exportação (soja, minério, petróleo, café, carnes, celulose...).
# MAGIC - **~33 mil eventos** de rastreamento de contêineres (JSON aninhado) de 8 armadores.
# MAGIC - Histórias "escondidas" nos dados para vocês descobrirem com Dashboard e Genie 🕵️:
# MAGIC   1. Um **boom de importação de veículos elétricos** a partir de 2025.
# MAGIC   2. Um **gargalo de desembaraço em um porto do Sul** nos últimos meses.
# MAGIC   3. Um **armador com atrasos crescentes** nas rotas da Ásia.
# MAGIC - Os arquivos brutos têm **problemas de qualidade propositais** (duplicidades, valores inválidos, países com grafias diferentes) para tratarmos na camada Silver.

# COMMAND ----------

import datetime as dt
import os

import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)
INICIO, FIM = dt.date(2024, 1, 1), dt.date(2026, 9, 30)
MESES = pd.period_range("2024-01", "2026-09", freq="M")


def escolha(opcoes):
    """Sorteia uma chave de um dicionário {opção: peso}."""
    chaves = list(opcoes)
    pesos = np.array(list(opcoes.values()), dtype=float)
    return chaves[rng.choice(len(chaves), p=pesos / pesos.sum())]


def cnpj():
    base = list(rng.integers(0, 10, 8)) + [0, 0, 0, 1]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        r = sum(d * p for d, p in zip(base, pesos)) % 11
        base.append(0 if r < 2 else 11 - r)
    s = "".join(map(str, base))
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


# ---------------------------------------------------------------- NCMs
# codigo: (descricao, categoria, fluxo, (usd_kg_min, max), (peso_min, max), paises, vias, aliquota_ii)
NCM = {
    "8541.43.00": ("Módulos fotovoltaicos (painéis solares)", "Energia", "I", (2.5, 4.0), (8e3, 6e4), {"China": 90, "Vietnã": 6, "Índia": 4}, {"Marítima": 1}, 0.106),
    "8507.60.00": ("Baterias de íon de lítio", "Energia", "I", (15, 25), (2e3, 2e4), {"China": 80, "Coreia do Sul": 12, "Japão": 8}, {"Marítima": 9, "Aérea": 1}, 0.18),
    "8517.13.00": ("Smartphones", "Eletroeletrônicos", "I", (150, 300), (200, 3e3), {"China": 70, "Vietnã": 20, "Índia": 10}, {"Aérea": 6, "Marítima": 4}, 0.16),
    "8471.30.12": ("Notebooks e computadores portáteis", "Eletroeletrônicos", "I", (80, 150), (500, 5e3), {"China": 80, "Vietnã": 15, "Taiwan": 5}, {"Marítima": 7, "Aérea": 3}, 0.16),
    "8542.31.90": ("Circuitos integrados (processadores)", "Eletroeletrônicos", "I", (800, 2000), (10, 300), {"Taiwan": 35, "China": 25, "Coreia do Sul": 20, "Estados Unidos": 20}, {"Aérea": 19, "Marítima": 1}, 0.0),
    "8529.90.20": ("Partes de receptores de TV (ZFM)", "Eletroeletrônicos", "I", (20, 40), (2e3, 2e4), {"China": 70, "Coreia do Sul": 20, "Vietnã": 10}, {"Marítima": 8, "Aérea": 2}, 0.14),
    "3102.10.10": ("Ureia fertilizante", "Fertilizantes", "I", (0.3, 0.5), (3e6, 3e7), {"Rússia": 35, "Catar": 20, "Nigéria": 15, "Argélia": 15, "China": 15}, {"Marítima": 1}, 0.0),
    "3104.20.10": ("Cloreto de potássio", "Fertilizantes", "I", (0.25, 0.45), (5e6, 4e7), {"Canadá": 45, "Rússia": 30, "Belarus": 25}, {"Marítima": 1}, 0.0),
    "3105.30.00": ("Fosfato diamônico (DAP)", "Fertilizantes", "I", (0.5, 0.8), (2e6, 2e7), {"Marrocos": 50, "Rússia": 20, "China": 20, "Estados Unidos": 10}, {"Marítima": 1}, 0.0),
    "3808.91.99": ("Inseticidas para agricultura", "Agroquímicos", "I", (5, 12), (5e3, 5e4), {"China": 60, "Índia": 30, "Estados Unidos": 10}, {"Marítima": 1}, 0.08),
    "3004.90.69": ("Medicamentos em doses", "Farmacêutico", "I", (100, 400), (100, 3e3), {"Estados Unidos": 30, "Alemanha": 25, "Suíça": 20, "Índia": 15, "Irlanda": 10}, {"Aérea": 7, "Marítima": 3}, 0.08),
    "2941.10.20": ("Amoxicilina (insumo farmacêutico)", "Farmacêutico", "I", (20, 50), (500, 1e4), {"China": 60, "Índia": 40}, {"Marítima": 7, "Aérea": 3}, 0.02),
    "8703.80.00": ("Veículos elétricos", "Automotivo", "I", (15, 25), (2e4, 5e5), {"China": 85, "Alemanha": 10, "Estados Unidos": 5}, {"Marítima": 1}, 0.18),
    "8703.23.10": ("Automóveis 1.500 a 3.000 cm³", "Automotivo", "I", (12, 20), (1e4, 2e5), {"Argentina": 40, "México": 30, "Alemanha": 15, "Japão": 15}, {"Rodoviária": 4, "Marítima": 6}, 0.35),
    "8708.99.90": ("Partes e acessórios de veículos", "Automotivo", "I", (6, 15), (2e3, 4e4), {"China": 30, "Alemanha": 20, "Argentina": 20, "Japão": 15, "Estados Unidos": 15}, {"Marítima": 7, "Rodoviária": 2, "Aérea": 1}, 0.16),
    "8429.52.12": ("Escavadeiras hidráulicas", "Máquinas e equipamentos", "I", (8, 15), (1.5e4, 1e5), {"China": 40, "Japão": 25, "Estados Unidos": 20, "Coreia do Sul": 15}, {"Marítima": 1}, 0.14),
    "8479.89.99": ("Máquinas e aparelhos mecânicos", "Máquinas e equipamentos", "I", (20, 60), (1e3, 2e4), {"Alemanha": 30, "China": 30, "Itália": 25, "Estados Unidos": 15}, {"Marítima": 8, "Aérea": 2}, 0.14),
    "2710.19.21": ("Óleo diesel", "Combustíveis", "I", (0.6, 0.9), (1e7, 5e7), {"Estados Unidos": 50, "Rússia": 35, "Índia": 15}, {"Marítima": 1}, 0.0),
    "3902.10.20": ("Polipropileno em formas primárias", "Químico", "I", (1.0, 1.6), (2e4, 2e5), {"Estados Unidos": 30, "Arábia Saudita": 20, "Coreia do Sul": 20, "China": 15, "Argentina": 15}, {"Marítima": 1}, 0.126),
    "2905.11.00": ("Metanol", "Químico", "I", (0.3, 0.5), (1e6, 1e7), {"Chile": 30, "Trinidad e Tobago": 30, "Estados Unidos": 20, "Arábia Saudita": 20}, {"Marítima": 1}, 0.0),
    "6403.99.90": ("Calçados", "Bens de consumo", "I", (20, 40), (2e3, 1.5e4), {"China": 50, "Vietnã": 40, "Indonésia": 10}, {"Marítima": 1}, 0.35),
    "9503.00.99": ("Brinquedos", "Bens de consumo", "I", (5, 12), (3e3, 2e4), {"China": 90, "Vietnã": 10}, {"Marítima": 1}, 0.20),
    "1001.99.00": ("Trigo", "Alimentos", "I", (0.25, 0.35), (3e6, 3e7), {"Argentina": 70, "Estados Unidos": 15, "Canadá": 10, "Uruguai": 5}, {"Marítima": 8, "Rodoviária": 2}, 0.0),
    "0302.14.00": ("Salmão fresco", "Alimentos", "I", (8, 12), (5e3, 3e4), {"Chile": 95, "Noruega": 5}, {"Rodoviária": 6, "Aérea": 4}, 0.10),
    # ---------------- exportação
    "1201.90.00": ("Soja em grãos", "Agronegócio", "E", (0.38, 0.5), (1e6, 6e7), {"China": 70, "Espanha": 6, "Países Baixos": 6, "Tailândia": 6, "Turquia": 4, "Irã": 8}, {"Marítima": 1}, None),
    "2601.11.00": ("Minério de ferro", "Mineração", "E", (0.08, 0.12), (2e7, 1.5e8), {"China": 65, "Malásia": 10, "Japão": 10, "Omã": 5, "Países Baixos": 10}, {"Marítima": 1}, None),
    "2709.00.10": ("Petróleo bruto", "Petróleo e gás", "E", (0.45, 0.6), (5e7, 1.5e8), {"China": 45, "Estados Unidos": 15, "Espanha": 10, "Índia": 10, "Países Baixos": 20}, {"Marítima": 1}, None),
    "0901.11.10": ("Café em grão não torrado", "Agronegócio", "E", (3.5, 6.0), (1e5, 1e6), {"Estados Unidos": 25, "Alemanha": 20, "Itália": 12, "Bélgica": 12, "Japão": 11, "Turquia": 10, "Colômbia": 10}, {"Marítima": 1}, None),
    "1701.14.00": ("Açúcar de cana", "Agronegócio", "E", (0.4, 0.55), (5e6, 4e7), {"China": 20, "Argélia": 15, "Bangladesh": 15, "Índia": 10, "Marrocos": 10, "Nigéria": 10, "Arábia Saudita": 20}, {"Marítima": 1}, None),
    "0202.30.00": ("Carne bovina congelada desossada", "Proteína animal", "E", (4.5, 6.5), (2.5e4, 1e5), {"China": 50, "Estados Unidos": 15, "Chile": 10, "Egito": 10, "Hong Kong": 15}, {"Marítima": 1}, None),
    "0207.14.00": ("Pedaços de frango congelados", "Proteína animal", "E", (1.8, 2.8), (2.5e4, 1e5), {"China": 20, "Japão": 15, "Arábia Saudita": 20, "Emirados Árabes Unidos": 15, "África do Sul": 15, "Países Baixos": 15}, {"Marítima": 1}, None),
    "4703.29.00": ("Celulose branqueada de eucalipto", "Florestal", "E", (0.5, 0.75), (1e6, 2e7), {"China": 45, "Estados Unidos": 20, "Países Baixos": 15, "Itália": 10, "Bélgica": 10}, {"Marítima": 1}, None),
    "1005.90.10": ("Milho em grão", "Agronegócio", "E", (0.18, 0.25), (1e7, 6e7), {"China": 30, "Japão": 10, "Vietnã": 15, "Egito": 15, "Irã": 15, "Coreia do Sul": 15}, {"Marítima": 1}, None),
    "5201.00.20": ("Algodão não cardado", "Agronegócio", "E", (1.6, 2.0), (1e5, 2e6), {"China": 30, "Vietnã": 20, "Bangladesh": 15, "Paquistão": 15, "Turquia": 10, "Indonésia": 10}, {"Marítima": 1}, None),
    "2009.11.00": ("Suco de laranja congelado", "Agronegócio", "E", (1.5, 3.0), (2e5, 3e6), {"Bélgica": 40, "Estados Unidos": 35, "Países Baixos": 15, "Japão": 10}, {"Marítima": 1}, None),
    "7207.12.00": ("Semimanufaturados de aço", "Siderurgia", "E", (0.5, 0.7), (1e6, 2e7), {"Estados Unidos": 40, "México": 20, "Canadá": 15, "Turquia": 15, "Argentina": 10}, {"Marítima": 1}, None),
    "8802.40.90": ("Aviões comerciais", "Aeroespacial", "E", (1500, 2500), (3e4, 4e4), {"Estados Unidos": 60, "Países Baixos": 15, "Canadá": 10, "Japão": 15}, {"Aérea": 1}, None),
}

ncm_df = pd.DataFrame([
    {"codigo_ncm": k, "descricao": v[0], "categoria": v[1], "capitulo": k[:2],
     "fluxo_predominante": "Importação" if v[2] == "I" else "Exportação",
     "aliquota_ii": v[7] if v[7] is not None else ""}
    for k, v in NCM.items()
])

# ---------------------------------------------------------------- empresas
UF_PESO = {"SP": 34, "PR": 12, "SC": 11, "RJ": 8, "MG": 8, "RS": 8, "ES": 4, "AM": 5, "BA": 3, "PE": 3, "GO": 2, "MT": 2}
NOMES_A = ["Atlântica", "Paranaense", "Horizonte", "Vale Sul", "Iguaçu", "Costa Verde", "Planalto", "Meridiano",
           "Aurora", "Rota Norte", "Litoral", "Serra Azul", "Bandeirante", "Pampa", "Amazônia", "Capixaba",
           "Guaíra", "Alvorada", "Terra Nova", "Porto Alto", "Cerrado", "Ipiranga", "Tropical", "Cruzeiro"]
NOMES_B = {"Energia": ["Solar", "Energia", "Power"], "Eletroeletrônicos": ["Tech", "Eletrônicos", "Digital"],
           "Fertilizantes": ["Fertilizantes", "Agro Nutrientes"], "Agroquímicos": ["Agroquímica", "Defensivos"],
           "Farmacêutico": ["Farma", "Pharma", "Saúde"], "Automotivo": ["Motors", "Autopeças", "Veículos"],
           "Máquinas e equipamentos": ["Máquinas", "Equipamentos", "Industrial"], "Combustíveis": ["Combustíveis", "Petro"],
           "Químico": ["Química", "Polímeros", "Petroquímica"], "Bens de consumo": ["Comercial", "Varejo", "Importadora"],
           "Alimentos": ["Alimentos", "Moinhos", "Foods"], "Agronegócio": ["Agro", "Grãos", "Cereais"],
           "Mineração": ["Mineração", "Minérios"], "Petróleo e gás": ["Óleo e Gás", "Energia"],
           "Proteína animal": ["Frigorífico", "Carnes", "Proteínas"], "Florestal": ["Celulose", "Florestal"],
           "Siderurgia": ["Aços", "Siderúrgica"], "Aeroespacial": ["Aeroespacial"]}
SUFIXOS = ["Ltda", "S.A.", "Importação e Exportação Ltda", "Comércio Exterior Ltda", "Indústria e Comércio S.A."]
PORTE = {"Pequena": 25, "Média": 40, "Grande": 35}

empresas, nomes_usados = [], set()
cat_import = sorted({v[1] for v in NCM.values() if v[2] == "I"})
cat_export = sorted({v[1] for v in NCM.values() if v[2] == "E"})
for i in range(380):
    exportadora = i >= 260
    setor = cat_export[i % len(cat_export)] if exportadora else cat_import[i % len(cat_import)]
    while True:
        nome = f"{rng.choice(NOMES_A)} {rng.choice(NOMES_B[setor])} {rng.choice(SUFIXOS)}"
        if nome not in nomes_usados:
            nomes_usados.add(nome)
            break
    uf = escolha(UF_PESO)
    if setor == "Eletroeletrônicos" and rng.random() < 0.5:
        uf = "AM"  # Zona Franca de Manaus
    empresas.append({"cnpj": cnpj(), "razao_social": nome, "uf": uf, "setor": setor,
                     "porte": escolha(PORTE), "perfil": "Exportador" if exportadora else "Importador",
                     "data_cadastro": str(dt.date(2015, 1, 1) + dt.timedelta(days=int(rng.integers(0, 3200))))})
emp_df = pd.DataFrame(empresas)
importadores = emp_df[emp_df.perfil == "Importador"]
exportadores = emp_df[emp_df.perfil == "Exportador"]
# "tamanho" do importador (lei de potência → poucos grandes concentram o volume)
peso_emp = {c: float(rng.pareto(1.3) + 0.2) for c in emp_df.cnpj}

# ---------------------------------------------------------------- portos e logística
PORTOS_UF = {
    "SP": {"Porto de Santos": 80, "Porto de Paranaguá": 10, "Porto do Rio de Janeiro": 10},
    "PR": {"Porto de Paranaguá": 80, "Porto de Itajaí": 10, "Porto de Santos": 10},
    "SC": {"Porto de Itajaí": 45, "Porto de Navegantes": 40, "Porto de Paranaguá": 15},
    "RS": {"Porto de Rio Grande": 85, "Porto de Itajaí": 15},
    "RJ": {"Porto do Rio de Janeiro": 75, "Porto de Santos": 25},
    "MG": {"Porto do Rio de Janeiro": 40, "Porto de Santos": 35, "Porto de Vitória": 25},
    "ES": {"Porto de Vitória": 90, "Porto do Rio de Janeiro": 10},
    "AM": {"Porto de Manaus": 95, "Porto de Santos": 5},
    "BA": {"Porto de Salvador": 80, "Porto de Suape": 20},
    "PE": {"Porto de Suape": 90, "Porto de Salvador": 10},
    "GO": {"Porto de Santos": 60, "Porto de Paranaguá": 25, "Porto de Vitória": 15},
    "MT": {"Porto de Paranaguá": 50, "Porto de Santos": 50},
}
AEROPORTOS = {"Aeroporto de Guarulhos": 55, "Aeroporto de Viracopos": 45}
FRONTEIRAS = {"Uruguaiana (fronteira rodoviária)": 55, "Foz do Iguaçu (fronteira rodoviária)": 45}
PORTOS_EXPORT = {
    "Agronegócio": {"Porto de Santos": 45, "Porto de Paranaguá": 25, "Porto de Rio Grande": 12, "Porto do Itaqui": 18},
    "Mineração": {"Porto de Tubarão": 50, "Terminal de Ponta da Madeira": 50},
    "Petróleo e gás": {"Terminal offshore Bacia de Santos": 70, "Terminal de São Sebastião": 30},
    "Proteína animal": {"Porto de Santos": 35, "Porto de Paranaguá": 25, "Porto de Itajaí": 25, "Porto de Rio Grande": 15},
    "Florestal": {"Porto de Santos": 40, "Porto de Vitória": 35, "Porto de Rio Grande": 25},
    "Siderurgia": {"Porto de Vitória": 50, "Porto do Rio de Janeiro": 50},
    "Aeroespacial": {"Aeroporto de São José dos Campos": 1},
}
ARMADORES = {"MSC": ("MSCU", 24), "Maersk": ("MAEU", 20), "CMA CGM": ("CMAU", 14), "Hapag-Lloyd": ("HLXU", 12),
             "COSCO": ("CSNU", 10), "ONE": ("ONEU", 8), "Evergreen": ("EGHU", 7), "ZIM": ("ZIMU", 5)}
NAVIOS = {a: [f"{a.split()[0].upper()} {n}" for n in rng.choice(
    ["AURORA", "VALENCIA", "SANTOS", "PACIFIC", "ATLANTIC", "ORION", "LIBRA", "VEGA", "ANDES", "TAURUS",
     "HELENA", "SOFIA", "RIO", "ESMERALDA", "CORAL", "POLARIS"], 4, replace=False)] for a in ARMADORES}
ORIGEM_PAIS = {"China": ["Xangai", "Ningbo", "Shenzhen", "Qingdao"], "Vietnã": ["Ho Chi Minh"], "Índia": ["Nhava Sheva"],
               "Coreia do Sul": ["Busan"], "Japão": ["Yokohama"], "Taiwan": ["Kaohsiung"], "Alemanha": ["Hamburgo"],
               "Itália": ["Gênova"], "Estados Unidos": ["Houston", "Savannah"], "Suíça": ["Roterdã"], "Irlanda": ["Roterdã"],
               "México": ["Veracruz"], "Indonésia": ["Jacarta"], "Argentina": ["Buenos Aires"], "Arábia Saudita": ["Jeddah"],
               "Chile": ["San Antonio"], "Canadá": ["Vancouver"], "Uruguai": ["Montevidéu"]}
TRANSIT_BASE = {"Xangai": 38, "Ningbo": 39, "Shenzhen": 36, "Qingdao": 41, "Ho Chi Minh": 34, "Nhava Sheva": 30,
                "Busan": 40, "Yokohama": 42, "Kaohsiung": 37, "Hamburgo": 23, "Gênova": 21, "Roterdã": 22,
                "Houston": 19, "Savannah": 17, "Veracruz": 20, "Jacarta": 36, "Buenos Aires": 4, "Jeddah": 28,
                "San Antonio": 12, "Vancouver": 30, "Montevidéu": 3}
ASIA = {"Xangai", "Ningbo", "Shenzhen", "Qingdao", "Ho Chi Minh", "Busan", "Yokohama", "Kaohsiung", "Jacarta"}


def mes_idx(d):
    return (d.year - 2024) * 12 + d.month - 1


# ---------------------------------------------------------------- câmbio PTAX
dias = pd.bdate_range(INICIO, FIM)
ptax = 4.90 + np.cumsum(rng.normal(0.0016, 0.028, len(dias)))
ptax = np.clip(ptax, 4.75, 6.35)
cambio_df = pd.DataFrame({"data": dias.strftime("%Y-%m-%d"), "moeda": "USD", "taxa_compra": ptax.round(4),
                          "taxa_venda": (ptax + 0.0006).round(4)})

print(f"NCMs: {len(ncm_df)} | empresas: {len(emp_df)} | dias de câmbio: {len(cambio_df)}")

# COMMAND ----------

# ---------------------------------------------------------------- DIs de importação
ncm_import = [k for k, v in NCM.items() if v[2] == "I"]
ncm_export = [k for k, v in NCM.items() if v[2] == "E"]
imp_por_setor = {s: importadores[importadores.setor == s] for s in cat_import}


def fator_ncm(ncm, i):
    """Multiplicador de volume por NCM ao longo do tempo (histórias dos dados)."""
    if ncm == "8703.80.00":                      # boom de veículos elétricos a partir de 2025
        return 0.25 if i < 12 else 0.6 + 0.09 * (i - 12)
    if ncm == "8541.43.00":                      # painéis solares: alto, desacelerando
        return 1.5 - 0.02 * i
    if NCM[ncm][1] == "Fertilizantes":           # sazonalidade da safra (pico jun-out)
        return 1.0 + 0.6 * np.sin((i % 12 - 3) / 12 * 2 * np.pi)
    return 1.0


def canal_e_dias(porto, via, i):
    gargalo = porto == "Porto de Paranaguá" and i >= 29  # jun/2026 em diante
    pesos = {"Verde": 84, "Amarelo": 9, "Vermelho": 6, "Cinza": 1}
    if gargalo:
        pesos = {"Verde": 70, "Amarelo": 14, "Vermelho": 14, "Cinza": 2}
    canal = escolha(pesos)
    base = {"Verde": (0.5, 2.0), "Amarelo": (2.5, 6.0), "Vermelho": (5.0, 15.0), "Cinza": (15.0, 40.0)}[canal]
    dias = rng.uniform(*base) * (0.5 if via == "Aérea" else 1.0) * (1.9 if gargalo else 1.0)
    return canal, max(1, int(round(dias)))


dis, seq = [], 1_000_000
for i, mes in enumerate(MESES):
    tendencia = (1 + 0.007 * i) * (1 + 0.08 * np.sin((mes.month - 3) / 12 * 2 * np.pi))
    for ncm in ncm_import:
        desc, cat, _, (pmin, pmax), (wmin, wmax), paises, vias, _ = NCM[ncm]
        n = rng.poisson(62 * tendencia * fator_ncm(ncm, i) * (0.35 if wmin >= 1e6 else 1.0))
        candidatos = imp_por_setor[cat]
        pesos = np.array([peso_emp[c] for c in candidatos.cnpj])
        for _ in range(n):
            emp = candidatos.iloc[rng.choice(len(candidatos), p=pesos / pesos.sum())]
            data = mes.start_time.date() + dt.timedelta(days=int(rng.integers(0, mes.days_in_month)))
            via = escolha(vias)
            pais = escolha(paises)
            if via == "Rodoviária" and pais not in ("Argentina", "Chile", "Uruguai"):
                via = "Marítima"
            porto = escolha(AEROPORTOS) if via == "Aérea" else escolha(FRONTEIRAS) if via == "Rodoviária" else escolha(PORTOS_UF[emp.uf])
            peso = float(np.exp(rng.uniform(np.log(wmin), np.log(wmax))))
            preco = rng.uniform(pmin, pmax) * (1 + 0.004 * i)
            fob = peso * preco
            frete = fob * (rng.uniform(0.02, 0.06) if via == "Marítima" else rng.uniform(0.06, 0.14) if via == "Aérea" else rng.uniform(0.02, 0.04))
            canal, dias_desemb = canal_e_dias(porto, via, i)
            desemb = data + dt.timedelta(days=dias_desemb)
            seq += int(rng.integers(1, 40))
            armador = escolha({a: p for a, (_, p) in ARMADORES.items()}) if via == "Marítima" and peso < 2e6 else ""
            dis.append({
                "numero_di": f"{str(data.year)[2:]}/{seq:07d}-{seq % 10}",
                "data_registro": data.isoformat(),
                "cnpj_importador": emp.cnpj,
                "ncm": ncm,
                "pais_origem": pais,
                "urf_despacho": porto,
                "via_transporte": via,
                "incoterm": escolha({"FOB": 45, "CIF": 20, "CFR": 15, "EXW": 10, "FCA": 10}),
                "valor_fob_usd": round(fob, 2),
                "frete_usd": round(frete, 2),
                "seguro_usd": round(fob * rng.uniform(0.001, 0.004), 2),
                "peso_liquido_kg": round(peso, 1),
                "canal_parametrizacao": canal,
                "data_desembaraco": desemb.isoformat() if desemb <= dt.date(2026, 10, 1) else "",
                "armador": armador,
                "qtd_containers": int(max(1, peso // 18000)) if armador else 0,
            })

imp_df = pd.DataFrame(dis)

# 🧪 Problemas de qualidade propositais (para a camada Silver)
sujos = imp_df.sample(frac=0.03, random_state=1).index
imp_df.loc[sujos[: len(sujos) // 3], "pais_origem"] = imp_df.loc[sujos[: len(sujos) // 3], "pais_origem"].str.upper() + " "
imp_df.loc[sujos[len(sujos) // 3:], "pais_origem"] = imp_df.loc[sujos[len(sujos) // 3:], "pais_origem"].str.lower()
invalidos = imp_df.sample(frac=0.004, random_state=2).index
imp_df.loc[invalidos, "valor_fob_usd"] = -imp_df.loc[invalidos, "valor_fob_usd"]
imp_df.loc[imp_df.sample(frac=0.002, random_state=3).index, "ncm"] = ""
imp_df = pd.concat([imp_df, imp_df.sample(frac=0.01, random_state=4)]).sort_values("data_registro").reset_index(drop=True)
print(f"DIs de importação: {len(imp_df):,}")

# COMMAND ----------

# ---------------------------------------------------------------- DU-Es de exportação
exp_por_setor = {s: exportadores[exportadores.setor == s] for s in cat_export}
dues, seq = [], 500_000
for i, mes in enumerate(MESES):
    for ncm in ncm_export:
        desc, cat, _, (pmin, pmax), (wmin, wmax), paises, vias, _ = NCM[ncm]
        safra = 1.0 + (0.7 * np.sin((mes.month - 1) / 12 * 2 * np.pi) if ncm in ("1201.90.00", "1005.90.10") else 0)
        n = rng.poisson((2 if ncm == "8802.40.90" else 46) * safra * (1 + 0.005 * i))
        candidatos = exp_por_setor[cat]
        pesos = np.array([peso_emp[c] for c in candidatos.cnpj])
        for _ in range(n):
            emp = candidatos.iloc[rng.choice(len(candidatos), p=pesos / pesos.sum())]
            data = mes.start_time.date() + dt.timedelta(days=int(rng.integers(0, mes.days_in_month)))
            peso = float(np.exp(rng.uniform(np.log(wmin), np.log(wmax))))
            seq += int(rng.integers(1, 30))
            dues.append({
                "numero_due": f"{str(data.year)[2:]}BR{seq:010d}",
                "data_embarque": data.isoformat(),
                "cnpj_exportador": emp.cnpj,
                "ncm": ncm,
                "pais_destino": escolha(paises),
                "porto_embarque": escolha(PORTOS_EXPORT.get(cat, {"Porto de Santos": 1})),
                "via_transporte": escolha(vias),
                "valor_fob_usd": round(peso * rng.uniform(pmin, pmax), 2),
                "peso_liquido_kg": round(peso, 1),
                "uf_produtor": emp.uf,
            })
exp_df = pd.DataFrame(dues)
exp_df = pd.concat([exp_df, exp_df.sample(frac=0.008, random_state=5)]).sort_values("data_embarque").reset_index(drop=True)
print(f"DU-Es de exportação: {len(exp_df):,}")

# COMMAND ----------

# ---------------------------------------------------------------- eventos de rastreamento (JSON aninhado)
HOJE = dt.datetime(2026, 9, 30, 18, 0)
maritimas = imp_df[(imp_df.armador != "") & (imp_df.data_registro >= "2025-01-01")].drop_duplicates("numero_di")
amostra = maritimas.sample(n=min(5200, len(maritimas)), random_state=7)
eventos = []
for _, di in amostra.iterrows():
    armador = di.armador
    prefixo = ARMADORES[armador][0]
    origens = ORIGEM_PAIS.get(di.pais_origem, ["Roterdã"])
    origem = origens[int(rng.integers(0, len(origens)))]
    destino = di.urf_despacho
    base = TRANSIT_BASE[origem]
    chegada_prev = dt.datetime.fromisoformat(di.data_registro) + dt.timedelta(hours=int(rng.integers(-36, 12)))
    partida = chegada_prev - dt.timedelta(days=base)
    atraso = max(0.0, rng.normal(1.5, 2.5))
    meses_2025 = (partida.year - 2025) * 12 + partida.month
    if armador == "ZIM" and origem in ASIA:          # armador com atrasos crescentes na Ásia
        atraso += max(0, meses_2025 - 10) * 0.9 + rng.uniform(0, 4)
    if destino == "Porto de Paranaguá" and partida >= dt.datetime(2026, 5, 1):
        atraso += rng.uniform(2, 6)                    # fila de atracação
    chegada = partida + dt.timedelta(days=base + atraso)
    container = f"{prefixo}{int(rng.integers(1_000_000, 9_999_999))}"
    bl = f"{prefixo[:3]}{int(rng.integers(100_000_000, 999_999_999))}"
    navio = NAVIOS[armador][int(rng.integers(0, 4))]
    marcos = [("GATE_IN", "Contêiner recebido no terminal de origem", origem, partida - dt.timedelta(days=float(rng.uniform(2, 5)))),
              ("EMBARQUE", "Contêiner embarcado no navio", origem, partida - dt.timedelta(hours=float(rng.uniform(6, 30)))),
              ("PARTIDA", "Navio partiu do porto de origem", origem, partida)]
    if origem in ASIA and rng.random() < 0.45:
        marcos.append(("TRANSBORDO", "Transbordo em porto intermediário", "Singapura", partida + dt.timedelta(days=base * 0.3)))
    marcos += [("CHEGADA", "Navio atracou no porto de destino", destino, chegada),
               ("DESCARGA", "Contêiner descarregado", destino, chegada + dt.timedelta(hours=float(rng.uniform(8, 40)))),
               ("GATE_OUT", "Contêiner retirado do terminal", destino, chegada + dt.timedelta(days=float(rng.uniform(2, 8))))]
    for codigo, descricao, local, quando in marcos:
        if quando > HOJE:
            break
        eventos.append({
            "id_evento": f"EV{len(eventos) + 1:08d}",
            "container": container, "bl": bl, "armador": armador,
            "navio": {"nome": navio, "imo": f"IMO{9_000_000 + sum(map(ord, navio)) * 37 % 999_999}"},
            "consignatario_cnpj": di.cnpj_importador,
            "rota": {"porto_origem": origem, "porto_destino": destino,
                     "eta_prevista": (partida + dt.timedelta(days=base)).strftime("%Y-%m-%dT%H:%M:%S")},
            "evento": {"codigo": codigo, "descricao": descricao, "local": local,
                       "data_hora": quando.strftime("%Y-%m-%dT%H:%M:%S")},
        })
ev_df = pd.DataFrame(eventos)
ev_df = pd.concat([ev_df, ev_df.sample(frac=0.015, random_state=8)]).reset_index(drop=True)  # eventos reenviados (duplicados)
print(f"Eventos de rastreamento: {len(ev_df):,} ({amostra.shape[0]:,} contêineres)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Gravação dos arquivos brutos na *landing zone*
# MAGIC
# MAGIC Simulamos o que chegaria de sistemas de origem (Siscomex, APIs de armadores, ERP):
# MAGIC ```
# MAGIC /Volumes/<catalogo>/<schema>/landing/
# MAGIC ├── importacoes/        → 1 CSV por mês (jan/2024 … ago/2026)
# MAGIC ├── exportacoes/        → 1 CSV por ano
# MAGIC ├── eventos_embarque/   → JSON Lines (1 arquivo por mês)
# MAGIC ├── referencias/        → empresas.csv, ncm.csv, cambio_ptax.csv
# MAGIC └── _chegando/          → arquivo de set/2026 que "vai chegar" durante o Lab 1
# MAGIC ```

# COMMAND ----------

import shutil

for sub in ["importacoes", "exportacoes", "eventos_embarque", "referencias", "_chegando"]:
    caminho = f"{LANDING}/{sub}"
    if os.path.exists(caminho):
        shutil.rmtree(caminho)
    os.makedirs(caminho, exist_ok=True)
if os.path.exists(CHECKPOINTS):
    shutil.rmtree(CHECKPOINTS)

imp_df["_mes"] = imp_df.data_registro.str[:7]
for mes, parte in imp_df.groupby("_mes"):
    pasta = "_chegando" if mes == "2026-09" else "importacoes"
    parte.drop(columns="_mes").to_csv(f"{LANDING}/{pasta}/importacoes_{mes.replace('-', '_')}.csv", index=False)

exp_df["_ano"] = exp_df.data_embarque.str[:4]
for ano, parte in exp_df.groupby("_ano"):
    parte.drop(columns="_ano").to_csv(f"{LANDING}/exportacoes/exportacoes_{ano}.csv", index=False)

ev_df["_mes"] = ev_df.evento.map(lambda e: e["data_hora"][:7])
for mes, parte in ev_df.groupby("_mes"):
    parte.drop(columns="_mes").to_json(f"{LANDING}/eventos_embarque/eventos_{mes.replace('-', '_')}.json",
                                       orient="records", lines=True, force_ascii=False)

emp_df.to_csv(f"{LANDING}/referencias/empresas.csv", index=False)
ncm_df.to_csv(f"{LANDING}/referencias/ncm.csv", index=False)
cambio_df.to_csv(f"{LANDING}/referencias/cambio_ptax.csv", index=False)

display(dbutils.fs.ls(LANDING))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. SQL Warehouse e Databricks App
# MAGIC
# MAGIC O warehouse será usado pelo Dashboard, pelo Genie e pelo App. O App é **criado agora**
# MAGIC (sem código ainda) porque o compute dele leva alguns minutos para ficar pronto — quando
# MAGIC chegarmos no Lab 4 ele já estará no ar esperando o deploy.

# COMMAND ----------

WAREHOUSE_ID = escolher_warehouse()
wh = w.warehouses.get(WAREHOUSE_ID)
print(f"🏭 SQL Warehouse: {wh.name} ({WAREHOUSE_ID}) — estado: {wh.state}")
if str(getattr(wh.state, "value", wh.state)) != "RUNNING":
    w.warehouses.start(WAREHOUSE_ID)  # acorda o warehouse para os próximos labs

try:
    app = api("GET", f"/api/2.0/apps/{APP_NAME}")
    print(f"🚀 App '{APP_NAME}' já existe (estado do compute: {app.get('compute_status', {}).get('state')})")
except Exception:
    app = api("POST", "/api/2.0/apps", {
        "name": APP_NAME,
        "description": "Radar Comex — app do Workshop LogComex x Databricks",
    })
    print(f"🚀 App '{APP_NAME}' criado — o compute está iniciando em segundo plano.")
cfg_set("app_name", APP_NAME)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. (Opcional) Modo *fast-track*
# MAGIC
# MAGIC Chegou atrasado ou algo deu errado? Mude o widget **fast_track** para `sim` e rode a célula
# MAGIC abaixo: ela executa o Lab 1 inteiro automaticamente, deixando as tabelas prontas para os Labs 2–4.

# COMMAND ----------

dbutils.widgets.dropdown("fast_track", "nao", ["nao", "sim"], "Executar Lab 1 automaticamente?")
if dbutils.widgets.get("fast_track") == "sim":
    print(dbutils.notebook.run("./01_Engenharia_de_Dados", 1800, {"catalogo": CATALOGO, "modo": "automatico"}))

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Setup concluído

# COMMAND ----------

resumo()
print(f"🏭 Warehouse ...... {WAREHOUSE_ID}")
print(f"\n✅ Setup concluído! Abra o notebook 01_Engenharia_de_Dados para começar o Lab 1.")
displayHTML(f"""
<div style="font-family:Poppins,Arial;background:{PRETO};color:white;padding:18px 24px;border-radius:12px;border-left:8px solid {ROXO}">
  <div style="font-size:20px;font-weight:700">✅ Ambiente pronto, {USUARIO.split('@')[0]}!</div>
  <div style="margin-top:6px">Schema <b style="color:{ROXO_CLARO}">{CATALOGO}.{SCHEMA}</b> · {len(imp_df):,} DIs · {len(exp_df):,} DU-Es · {len(ev_df):,} eventos de rastreamento</div>
  <div style="margin-top:6px">Próximo passo → <b>01_Engenharia_de_Dados</b></div>
</div>""")
