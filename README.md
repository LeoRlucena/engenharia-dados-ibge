# Projeto de Engenharia de Dados - IBGE

## Objetivo

Desenvolver um pipeline de engenharia de dados utilizando dados públicos do IBGE para analisar o nível de desenvolvimento das regiões brasileiras com base em indicadores econômicos e demográficos.

## Tecnologias Utilizadas

- Python
- Pandas
- PostgreSQL
- Docker
- Docker Compose
- Jupyter Notebook
- Matplotlib

## Endpoints da API IBGE

### População
https://apisidra.ibge.gov.br/values/t/6579/n3/all/v/9324/p/2023?formato=json

Retorna:
- população estimada por estado
- ano de referência: 2023

---

### PIB
https://apisidra.ibge.gov.br/values/t/5938/n3/all/v/37/p/2023?formato=json

Retorna:
- PIB por estado
- ano de referência: 2023

---

### Estados
https://servicodados.ibge.gov.br/api/v1/localidades/estados

Retorna:
- nome do estado
- sigla
- região

---

### Regiões
https://servicodados.ibge.gov.br/api/v1/localidades/regioes

Retorna:
- regiões do Brasil

## Estrutura do Projeto

### docker/

Responsável pela infraestrutura do projeto.

Contém:
- configurações do PostgreSQL
- volumes
- scripts de inicialização do banco

### notebooks/

Responsável pela documentação e análise dos dados.

Arquivos:
- analise.ipynb → exploração e análise dos dados
- documentacao.ipynb → documentação técnica do pipeline

### src/extract/

Responsável pela coleta dos dados da API do IBGE.

Arquivo:
- ibge_api.py

Funções esperadas:
- consumir endpoints
- retornar JSON
- salvar dados brutos

### src/transform/

Responsável pelo tratamento e transformação dos dados.

Arquivo:
- tratamento.py

Funções esperadas:
- limpeza dos dados
- remoção de metadata
- padronização
- cálculo de PIB per capita
- criação dos DataFrames finais

### src/load/

Responsável pela carga dos dados no PostgreSQL.

Arquivo:
- postgres_loader.py

Funções esperadas:
- conexão com banco
- criação de tabelas
- inserção de dados

### src/visualization/

Responsável pela geração de gráficos e visualizações.

Arquivo:
- graficos.py

Funções esperadas:
- gráficos de PIB
- gráficos populacionais
- ranking por PIB per capita

### data/raw/

Armazena os dados brutos coletados da API.

### data/processed/

Armazena os dados tratados e padronizados.

### data/exports/

Armazena exportações finais em CSV.

## Pipeline de Dados

1. Extração dos dados da API do IBGE
2. Transformação e limpeza
3. Armazenamento no PostgreSQL
4. Análise dos dados
5. Visualização dos resultados
6. Exportação CSV

## Objetivos Analíticos

- Identificar estados com maior PIB per capita
- Comparar regiões brasileiras
- Relacionar população e desenvolvimento econômico
- Gerar rankings econômicos