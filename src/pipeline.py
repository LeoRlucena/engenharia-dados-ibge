"""Orquestrador do pipeline end-to-end do projeto IBGE."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from src.extract.ibge_api import IBGEAPIClient
from src.load.postgres_loader import PostgresLoader
from src.transform.tratamento import TratamentoIBGE
from src.visualization.graficos import gerar_todos_graficos


DEFAULT_CONNECTION = "postgresql+psycopg2://postgres:postgres@postgres:5432/ibge_db"


def connection_string() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_CONNECTION)


def montar_indicadores_completos(
    fato: pd.DataFrame,
    estados: pd.DataFrame,
    regioes: pd.DataFrame,
) -> pd.DataFrame:
    """Monta uma tabela analítica única a partir dos DataFrames tratados."""
    fato_base = fato.drop(columns=["nome_estado"], errors="ignore")
    df = fato_base.merge(
        estados,
        left_on="codigo_estado",
        right_on="id_estado",
        how="left",
    )
    df = df.merge(regioes, on="id_regiao", how="left")
    return df.sort_values("ranking_pib_per_capita").reset_index(drop=True)


def exportar_resultados(df: pd.DataFrame, output_dir: str | Path = "data/exports") -> dict[str, Path]:
    """Exporta os CSVs finais usados na análise e apresentação."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    ranking_path = output / "ranking_desenvolvimento.csv"
    regioes_path = output / "indicadores_regiao.csv"

    df.sort_values("ranking_pib_per_capita").to_csv(
        ranking_path,
        index=False,
        encoding="utf-8",
    )

    indicadores_regiao = (
        df.groupby(["id_regiao", "sigla_regiao", "nome_regiao"], as_index=False)
        .agg(
            populacao=("populacao", "sum"),
            pib_mil_reais=("pib_mil_reais", "sum"),
            pib_per_capita_medio=("pib_per_capita", "mean"),
            quantidade_estados=("id_estado", "count"),
        )
        .sort_values("pib_per_capita_medio", ascending=False)
    )
    indicadores_regiao.to_csv(regioes_path, index=False, encoding="utf-8")

    return {
        "ranking": ranking_path,
        "regioes": regioes_path,
    }


def run_pipeline(
    ano_populacao: int = 2024,
    ano_pib: int = 2023,
    skip_db: bool = False,
    gerar_graficos: bool = True,
) -> dict[str, pd.DataFrame]:
    """Executa extração, transformação, carga, leitura, exportação e gráficos."""
    print("1/4 Extraindo dados da API do IBGE...")
    client = IBGEAPIClient()
    dados = client.extract_all(ano_populacao=ano_populacao, ano_pib=ano_pib)

    if skip_db:
        print("2/4 Transformando dados...")
        tratamento = TratamentoIBGE()
        dfs = tratamento.pipeline_tratamento(
            dados,
            ano_populacao=ano_populacao,
            ano_pib=ano_pib,
            salvar_csv=True,
        )
        indicadores = montar_indicadores_completos(
            dfs["fato_ibge"],
            dfs["dim_estado"],
            dfs["dim_regiao"],
        )
    else:
        print("2/4 Carregando dados no PostgreSQL...")
        loader = PostgresLoader(connection_string())
        dfs = loader.run_pipeline(dados, ano_populacao=ano_populacao, ano_pib=ano_pib)
        indicadores = loader.read_indicadores_completos()

    print("3/4 Exportando CSVs finais...")
    exportar_resultados(indicadores)

    if gerar_graficos:
        print("4/4 Gerando gráficos...")
        gerar_todos_graficos(indicadores)

    print("Pipeline concluído.")
    return {
        **dfs,
        "indicadores_completos": indicadores,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa o pipeline IBGE end-to-end.")
    parser.add_argument("--ano-populacao", type=int, default=2024)
    parser.add_argument("--ano-pib", type=int, default=2023)
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--sem-graficos", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        ano_populacao=args.ano_populacao,
        ano_pib=args.ano_pib,
        skip_db=args.skip_db,
        gerar_graficos=not args.sem_graficos,
    )
