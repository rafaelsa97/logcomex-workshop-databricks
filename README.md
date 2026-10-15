# Workshop LogComex × Databricks — hands-on

Workshop presencial para o time técnico de dados da LogComex. Numa tarde, cada participante constrói no
próprio ambiente Databricks uma solução de **inteligência de comércio exterior** completa: dos arquivos
brutos ao produto com IA.

```
Arquivos brutos ──▶ Engenharia de dados ──▶ AI/BI Dashboard ──▶ Genie ──▶ Databricks App
(DIs, DU-Es,         Bronze → Silver → Gold   painel "Radar Comex"  perguntas em   "Radar Comex": painéis +
 rastreamento)        no Unity Catalog                              português      chat com o Genie
```

Os dados são **100% sintéticos**, mas realistas: NCMs reais, portos, armadores, canais de parametrização,
câmbio PTAX e CNPJs válidos de empresas fictícias. Três histórias estão "escondidas" nos dados para
serem descobertas ao longo dos labs:

1. Um **boom de importação de veículos elétricos** a partir de 2025.
2. Um **gargalo de desembaraço em um porto do Sul** nos últimos meses.
3. Um **armador com atrasos crescentes** nas rotas da Ásia.

---

## Notebooks

Todos os notebooks rodam em **compute serverless** e não exigem nenhuma configuração manual. Os nomes de
schema, volume e app são derivados automaticamente do usuário de cada participante, então várias pessoas
podem fazer o workshop no mesmo workspace sem interferir umas nas outras.

| Notebook | Quem roda | Tempo | O que faz |
|---|---|---|---|
| `_config` | Ninguém (é chamado pelos demais) | – | Configuração compartilhada |
| `00_Setup` | Participante | ~3 min | Prepara todo o ambiente e gera os dados |
| `01_Engenharia_de_Dados` | Participante | 30 min | Bronze → Silver → Gold |
| `02_Dashboard_AIBI` | Participante | 30 min | Cria e explora o dashboard |
| `03_Genie` | Participante | 30 min | Cria e ensina o Genie space |
| `04_Databricks_Apps` | Participante | 25 min | Publica e altera o app |
| `05_Demo_Instrutor_App_React` | Instrutor (opcional) | ~5 min | Publica o mesmo app em React + FastAPI para a demo final |
| `99_Limpeza` | Participante (opcional) | 1 min | Remove o que o participante criou |
| `00_Instrutor_Preparacao` | Instrutor/admin (só em workspace compartilhado) | 1 min | Concede as permissões da turma |

### `_config`: configuração compartilhada
Executado automaticamente pelos outros notebooks (`%run ./_config`). Ele:
- detecta o catálogo padrão do workspace (o widget **catalogo** permite trocá-lo);
- define o schema `logcomex_ws_<usuario>`, o volume `landing` e o app `radar-comex-<usuario>`;
- guarda os IDs dos recursos criados (warehouse, dashboard, Genie) numa tabela de configuração para os labs seguintes.

### `00_Setup`: Lab 0, setup automatizado
Basta um **Run all**. O notebook:
- cria o schema e o volume do participante;
- gera os dados sintéticos de jan/2024 a set/2026:
  - ~47 mil DIs de importação;
  - ~20 mil DU-Es de exportação;
  - ~33 mil eventos de rastreamento de contêineres (JSON aninhado);
  - tabelas de referência: empresas, NCM e câmbio;
- grava os arquivos brutos (CSV e JSON) na *landing zone* com problemas de qualidade propositais, para serem tratados no Lab 1;
- escolhe um SQL Warehouse (prefere um serverless já existente; se não houver nenhum, cria um 2X-Small);
- cria antecipadamente o Databricks App, cujo compute leva alguns minutos para subir.

O widget **fast_track = sim** executa o Lab 1 inteiro automaticamente, para quem chegou atrasado ou teve algum problema.

### `01_Engenharia_de_Dados`: Lab 1, arquitetura medalhão
Executado célula a célula, com explicações:
- **Bronze:**
  - ingestão incremental com **Auto Loader**;
  - "chega" um arquivo novo durante o lab e só ele é processado;
  - leitura de CSV/JSON com `read_files` em SQL.
- **Silver:**
  - padronização dos países;
  - deduplicação;
  - conversão de tipos;
  - registros inválidos enviados para uma tabela de **quarentena**;
  - *constraint* de qualidade no Delta;
  - enriquecimento com empresas, NCM e câmbio.
- **Gold:**
  - tabelas de negócio: comércio exterior mensal, desempenho dos portos e status dos embarques;
  - primeira descoberta: o gargalo no porto.
- **Governança:**
  - comentários de colunas (que o Genie vai usar);
  - tags;
  - histórico e *time travel*;
  - linhagem no Unity Catalog.

### `02_Dashboard_AIBI`: Lab 2, AI/BI Dashboards
A primeira célula cria e publica o dashboard **"Radar Comex"**: 2 páginas, filtros globais e a identidade visual
da LogComex. Os exercícios cobrem:
- exploração com *cross-filtering*;
- criação de visualizações **com IA** a partir de linguagem natural;
- novos filtros e datasets;
- publicação, compartilhamento e agendamento de envio por e-mail.

### `03_Genie`: Lab 3, AI/BI Genie
A primeira célula cria o Genie space **"Radar Comex"**, já curado para comex:
- tabelas selecionadas;
- glossário em português (DI, DU-E, FOB/CIF, canais, lead time...);
- exemplos de SQL;
- perguntas sugeridas;
- *benchmarks*.

Os exercícios cobrem:
- perguntas livres e inspeção do SQL gerado;
- ensinar ao Genie um conceito de negócio novo ("operação crítica");
- criar uma medida reutilizável;
- avaliar a qualidade com benchmarks;
- integrar o Genie ao dashboard.

### `04_Databricks_Apps`: Lab 4, Databricks Apps
- Grava na pasta do participante o código do app **Radar Comex** (Streamlit), com 4 abas:
  - visão geral;
  - inteligência de NCM;
  - rastreamento de contêineres;
  - chat com o Genie.
- Dá ao *service principal* do app **apenas** as permissões necessárias (menor privilégio).
- Faz o deploy.

No exercício, o participante altera o `app.py` no editor do workspace (descomentando um bloco ou usando o
Databricks Assistant) e faz o redeploy.

### `05_Demo_Instrutor_App_React` (opcional, só o instrutor)
Publica o **mesmo Radar Comex reescrito como produto web**: frontend React (já compilado) e API FastAPI. Usa as
mesmas tabelas, o mesmo Genie space e as mesmas permissões mínimas do Lab 4. O instrutor o mostra no fechamento
do Lab 4, ao lado da versão Streamlit, para ilustrar o caminho "o time de dados prototipa em Python, o time de
produto entrega em React, na mesma plataforma".
- Precisa que os Labs 1–3 tenham sido concluídos pelo usuário que o executa.
- Cria um segundo app (`radar-react-<usuario>`), então conta na cota de apps do workspace.
- O deploy não roda `npm install` (o frontend vai pronto dentro do notebook) e leva o mesmo tempo do app Streamlit.

### `99_Limpeza` (opcional)
Com o widget **confirmar = sim**, remove **somente** o que foi criado para o participante: o app (e o app React
da demo, se existir), o Genie space, o dashboard e o schema (tabelas e volume).

### `00_Instrutor_Preparacao` (só em workspace compartilhado)
Rodado **uma vez pelo instrutor/admin** antes do workshop, quando todos usam o mesmo workspace:
- concede `USE CATALOG` e `CREATE SCHEMA` no catálogo para `account users`;
- concede `CAN_USE` no SQL Warehouse para o grupo `users`;
- verifica se Genie e Apps estão disponíveis e quantos apps já existem.

---

## Requisitos

### Modalidades de ambiente
- **A. Workspace próprio por participante:** cada pessoa usa o seu workspace, normalmente como admin. Basta atender aos requisitos abaixo.
- **B. Workspace compartilhado:** todos no mesmo workspace. O instrutor cadastra os participantes e roda o `00_Instrutor_Preparacao`.
  Cada pessoa continua isolada no próprio schema, dashboard, Genie space e app.

### Recursos do workspace
| Recurso | Usado em | Observação |
|---|---|---|
| **Unity Catalog** habilitado, com um catálogo onde se possa criar schemas | Todos os labs | Os notebooks detectam o catálogo padrão; se não houver um adequado, troque pelo widget `catalogo` |
| **Compute serverless para notebooks** | Todos os labs | Nenhum cluster precisa ser criado |
| **SQL Warehouse**, de preferência serverless | Labs 2, 3 e 4 | O setup reaproveita um existente ou cria um 2X-Small com auto-stop de 10 min |
| **AI/BI Dashboards** | Lab 2 | Habilitado por padrão |
| **AI/BI Genie** | Labs 3 e 4 | |
| **Databricks Assistant** (recursos de IA assistida) | Desafios dos Labs 1, 2 e 4 | Usado para criar gráficos com IA e alterar o código do app |
| **Databricks Apps** habilitado | Lab 4 | |
| **Cota de apps** suficiente | Lab 4 | 1 app por participante (+1 para a demo React do instrutor); confira o limite do workspace frente ao tamanho da turma |

### Privilégios de cada participante
| Privilégio | Para quê | Modalidade A (admin) | Modalidade B (compartilhado) |
|---|---|---|---|
| Usuário do workspace com os direitos **Workspace access** e **Databricks SQL access** | Notebooks, dashboard e Genie | ✔ já tem | O instrutor cadastra o usuário (os direitos vêm no grupo `users`) |
| Acesso ao **compute serverless** | Rodar os notebooks | ✔ | Padrão para usuários do workspace |
| `USE CATALOG` + `CREATE SCHEMA` no catálogo do workshop | Criar o próprio schema; como dono do schema, o participante cria tabelas e volume e concede leitura ao app | ✔ | Concedido pelo `00_Instrutor_Preparacao` |
| `CAN_USE` em um SQL Warehouse (ou permissão para criar um) | Dashboard, Genie e app | ✔ | Concedido pelo `00_Instrutor_Preparacao` |
| Permissão para **criar Databricks Apps** | Lab 4 | ✔ | Padrão para usuários do workspace com Apps habilitado |

O *service principal* do app de cada participante também precisa de permissões, que o próprio Lab 4 concede:
`SELECT` no schema do participante, `CAN_RUN` no Genie space dele e, conforme a modalidade:
- **A:** o participante (admin) concede `USE CATALOG` e `CAN_USE` no warehouse ao service principal;
- **B:** o `USE CATALOG` e o `CAN_USE` no warehouse vêm dos grants do instrutor para `account users` e `users`.

### Rede e equipamento
- Notebook com navegador atualizado (Chrome ou Edge). **Nenhuma instalação local** é necessária.
- Acesso, pela rede do local do workshop, à URL do workspace e ao domínio dos apps (`*.databricksapps.com`).
  Vale testar antes, porque proxies corporativos às vezes bloqueiam esse domínio.
- Os pacotes do app já vêm pré-instalados no Databricks Apps; não é preciso acessar pypi/npm.

### Conhecimento prévio
- SQL básico.
- Leitura de Python (os notebooks já vêm prontos; o participante executa, lê e faz pequenas alterações).
- Familiaridade com o vocabulário de comércio exterior, que o time da LogComex já domina.

### Após o workshop
Depois do workshop, rode o `99_Limpeza` (ou pare o app em *Compute → Apps*) para não deixar recursos ligados.

---

## Como preparar e executar

1. **Instrutor, uma semana antes:**
   - definir a modalidade (A ou B) e validar os requisitos acima;
   - na modalidade B, cadastrar os participantes e rodar o `00_Instrutor_Preparacao`;
   - enviar o link do workspace e o arquivo `LogComex_Workshop.dbc`.
2. **Instrutor, véspera:** rodar o fluxo completo com um usuário de teste (Setup → Lab 4, ~15 min) e, com o próprio
   usuário, o `05_Demo_Instrutor_App_React` (~5 min).
3. **Participante, na chegada:**
   1. No workspace, ir em **Workspace → Home → ⋮ → Import** e importar o `LogComex_Workshop.dbc`.
   2. Abrir o `00_Setup`, conectar ao compute **Serverless** e clicar em **Run all**.
4. **Durante os labs:** seguir os notebooks 01 → 04 na ordem. Cada lab cria automaticamente o que o seguinte precisa.

---

## Para quem mantém o material

- `src/notebooks/`: fontes dos notebooks (formato Databricks `.py`).
- `src/app/app.py`: app Streamlit "Radar Comex" (o build o embute em base64 no Lab 4).
- `src/app_react/`: versão React + FastAPI do app (demo do instrutor).
  - `backend/app.py`: API FastAPI, que também serve o frontend compilado em `backend/static/`;
  - `frontend/`: código React + Vite. Para recompilar: `cd src/app_react/frontend && npm install && npm run build`
    (gera `backend/static/`). Para desenvolver localmente, rode `uvicorn app:app` em `backend/` com as variáveis
    `WAREHOUSE_ID`, `CATALOGO`, `SCHEMA` e `GENIE_SPACE_ID` (e o perfil do CLI), e depois `npm run dev` no frontend.
- `build.py`: gera `dist/LogComex Workshop/` com os notebooks prontos, embutindo o app Streamlit no Lab 4 e o
  app React compilado (zip em base64) no notebook 05. Depois:
  `databricks workspace import-dir "dist/LogComex Workshop" "<pasta>" --overwrite` e
  `databricks workspace export "<pasta>" --format DBC --file dist/LogComex_Workshop.dbc`.
- `tools/teste_app.py`: teste headless do app (Streamlit AppTest) em job serverless.
