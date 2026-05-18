"""Loader para PostgreSQL."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine, text

from src.transform.tratamento import adicionar_clusterizacao

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PostgresLoader:
    """Responsável por criar tabelas e carregar dados no PostgreSQL."""

    def __init__(self, connection_string: str, processed_path: str | None = None):
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        if processed_path is None:
            project_root = Path(__file__).resolve().parents[2]
            self.processed_path = project_root / "data" / "processed"
        else:
            self.processed_path = Path(processed_path)
        self.processed_path.mkdir(parents=True, exist_ok=True)

    def _save_processed(self, filename: str, df: pd.DataFrame) -> Path:
        filepath = self.processed_path / filename
        df.to_csv(filepath, index=False, encoding="utf-8")
        logger.info("Arquivo processado salvo em: %s", filepath)
        return filepath

    def _row_params(self, row: pd.Series) -> Dict[str, Any]:
        return {str(key): (None if pd.isna(value) else value) for key, value in row.items()}

    def create_tables(self) -> None:
        """Cria as tabelas base do projeto."""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS dim_regiao (
                id_regiao INTEGER PRIMARY KEY,
                sigla_regiao VARCHAR(10),
                nome_regiao VARCHAR(100) UNIQUE NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS dim_estado (
                id_estado INTEGER PRIMARY KEY,
                sigla CHAR(2) UNIQUE NOT NULL,
                nome_estado VARCHAR(150) NOT NULL,
                id_regiao INTEGER REFERENCES dim_regiao(id_regiao)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fato_ibge (
                id_fato SERIAL PRIMARY KEY,
                id_estado INTEGER REFERENCES dim_estado(id_estado),
                ano_populacao INTEGER NOT NULL,
                ano_pib INTEGER NOT NULL,
                populacao BIGINT,
                pib_mil_reais NUMERIC(18,2),
                pib_per_capita NUMERIC(18,2),
                ranking_pib_per_capita INTEGER,
                cluster INTEGER,
                perfil_cluster VARCHAR(80),
                data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            ALTER TABLE fato_ibge
            ADD COLUMN IF NOT EXISTS ranking_pib_per_capita INTEGER
            """,
            """
            ALTER TABLE fato_ibge
            ADD COLUMN IF NOT EXISTS cluster INTEGER
            """,
            """
            ALTER TABLE fato_ibge
            ADD COLUMN IF NOT EXISTS perfil_cluster VARCHAR(80)
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_fato_ibge_estado_ano'
                ) THEN
                    ALTER TABLE fato_ibge
                    ADD CONSTRAINT uq_fato_ibge_estado_ano
                    UNIQUE (id_estado, ano_populacao, ano_pib);
                END IF;
            END
            $$;
            """,
        ]

        with self.engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))

        logger.info("Tabelas criadas com sucesso.")

    def load_regions(self, regioes: List[Dict[str, Any]]) -> pd.DataFrame:
        """Carrega regiões na dimensão de regiões."""
        registros = []

        for item in regioes:
            if not isinstance(item, dict):
                continue

            id_regiao = item.get("id")
            sigla_regiao = item.get("sigla")
            nome_regiao = item.get("nome")

            if id_regiao is not None and nome_regiao:
                registros.append(
                    {
                        "id_regiao": int(id_regiao),
                        "sigla_regiao": sigla_regiao,
                        "nome_regiao": nome_regiao,
                    }
                )

        df = pd.DataFrame(registros).drop_duplicates(subset=["id_regiao"])

        if not df.empty:
            with self.engine.begin() as conn:
                for _, row in df.iterrows():
                    conn.execute(
                        text(
                            """
                            INSERT INTO dim_regiao (id_regiao, sigla_regiao, nome_regiao)
                            VALUES (:id_regiao, :sigla_regiao, :nome_regiao)
                            ON CONFLICT (id_regiao)
                            DO UPDATE SET
                                sigla_regiao = EXCLUDED.sigla_regiao,
                                nome_regiao = EXCLUDED.nome_regiao
                            """
                        ),
                        self._row_params(row),
                    )

        self._save_processed("dim_regiao.csv", df)
        return df

    def load_states(self, estados: List[Dict[str, Any]]) -> pd.DataFrame:
        """Carrega estados na dimensão de estados."""
        registros = []

        for item in estados:
            if not isinstance(item, dict):
                continue

            id_estado = item.get("id")
            sigla = item.get("sigla")
            nome_estado = item.get("nome")
            regiao = item.get("regiao", {}) or {}

            id_regiao = regiao.get("id")

            if id_estado is not None and sigla and nome_estado:
                registros.append(
                    {
                        "id_estado": int(id_estado),
                        "sigla": sigla,
                        "nome_estado": nome_estado,
                        "id_regiao": int(id_regiao) if id_regiao is not None else None,
                    }
                )

        df = pd.DataFrame(registros).drop_duplicates(subset=["id_estado"])

        if not df.empty:
            with self.engine.begin() as conn:
                for _, row in df.iterrows():
                    conn.execute(
                        text(
                            """
                            INSERT INTO dim_estado (id_estado, sigla, nome_estado, id_regiao)
                            VALUES (:id_estado, :sigla, :nome_estado, :id_regiao)
                            ON CONFLICT (id_estado)
                            DO UPDATE SET
                                sigla = EXCLUDED.sigla,
                                nome_estado = EXCLUDED.nome_estado,
                                id_regiao = EXCLUDED.id_regiao
                            """
                        ),
                        self._row_params(row),
                    )

        self._save_processed("dim_estado.csv", df)
        return df

    def _to_dataframe(self, dados: List[Dict[str, Any]]) -> pd.DataFrame:
        if not dados:
            return pd.DataFrame()

        df = pd.DataFrame(dados)

        if df.empty:
            return df

        df = df.rename(columns={col: col.strip() for col in df.columns})
        return df

    def _extract_sidra_fact(
        self,
        dados: List[Dict[str, Any]],
        value_name: str,
    ) -> pd.DataFrame:
        """
        Converte o retorno do SIDRA em formato tabular com código do estado e valor.
        """
        df = self._to_dataframe(dados)

        if df.empty:
            return df

        if "D1C" not in df.columns or "V" not in df.columns:
            raise ValueError("Estrutura SIDRA inesperada: era esperado D1C e V.")

        base = df[["D1C", "D1N", "V"]].copy()
        base = base.rename(
            columns={
                "D1C": "codigo_estado",
                "D1N": "nome_estado",
                "V": value_name,
            }
        )

        base["codigo_estado"] = pd.to_numeric(base["codigo_estado"], errors="coerce")
        base[value_name] = (
            base[value_name]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        base[value_name] = pd.to_numeric(base[value_name], errors="coerce")

        base = base.dropna(subset=["codigo_estado", value_name]).copy()
        base["codigo_estado"] = base["codigo_estado"].astype(int)

        return base[["codigo_estado", "nome_estado", value_name]]

    def load_fact_data(
        self,
        populacao: List[Dict[str, Any]],
        pib: List[Dict[str, Any]],
        ano_populacao: int = 2024,
        ano_pib: int = 2023,
    ) -> pd.DataFrame:
        """Carrega a tabela fato com população e PIB."""
        pop_df = self._extract_sidra_fact(populacao, "populacao")
        pib_df = self._extract_sidra_fact(pib, "pib_mil_reais")

        if pop_df.empty or pib_df.empty:
            raise ValueError("Dados de população ou PIB vazios.")

        merged = pop_df.merge(
            pib_df[["codigo_estado", "pib_mil_reais"]],
            on="codigo_estado",
            how="inner",
            suffixes=("_pop", "_pib"),
        )

        estados_df = pd.read_sql(
            "SELECT id_estado, id_regiao, sigla, nome_estado FROM dim_estado",
            self.engine,
        )

        if estados_df.empty:
            raise ValueError("A dimensão de estados precisa ser carregada antes da fato.")

        merged = merged.merge(
            estados_df[["id_estado", "sigla", "nome_estado"]],
            left_on="codigo_estado",
            right_on="id_estado",
            how="left",
        )

        merged["pib_per_capita"] = merged["pib_mil_reais"] * 1000 / merged["populacao"]
        merged["ano_populacao"] = ano_populacao
        merged["ano_pib"] = ano_pib
        merged = adicionar_clusterizacao(merged)

        df_final = merged[
            [
                "id_estado",
                "ano_populacao",
                "ano_pib",
                "populacao",
                "pib_mil_reais",
                "pib_per_capita",
                "ranking_pib_per_capita",
                "cluster",
                "perfil_cluster",
            ]
        ].copy()

        df_final = df_final.dropna(subset=["id_estado"]).copy()
        df_final["id_estado"] = df_final["id_estado"].astype(int)
        df_final["populacao"] = df_final["populacao"].astype("Int64")
        df_final["pib_mil_reais"] = pd.to_numeric(df_final["pib_mil_reais"], errors="coerce")
        df_final["pib_per_capita"] = pd.to_numeric(df_final["pib_per_capita"], errors="coerce")
        df_final["ranking_pib_per_capita"] = df_final["ranking_pib_per_capita"].astype("Int64")
        df_final["cluster"] = df_final["cluster"].astype("Int64")

        if not df_final.empty:
            with self.engine.begin() as conn:
                for _, row in df_final.iterrows():
                    conn.execute(
                        text(
                            """
                            INSERT INTO fato_ibge (
                                id_estado,
                                ano_populacao,
                                ano_pib,
                                populacao,
                                pib_mil_reais,
                                pib_per_capita,
                                ranking_pib_per_capita,
                                cluster,
                                perfil_cluster
                            )
                            VALUES (
                                :id_estado,
                                :ano_populacao,
                                :ano_pib,
                                :populacao,
                                :pib_mil_reais,
                                :pib_per_capita,
                                :ranking_pib_per_capita,
                                :cluster,
                                :perfil_cluster
                            )
                            ON CONFLICT (id_estado, ano_populacao, ano_pib)
                            DO UPDATE SET
                                populacao = EXCLUDED.populacao,
                                pib_mil_reais = EXCLUDED.pib_mil_reais,
                                pib_per_capita = EXCLUDED.pib_per_capita,
                                ranking_pib_per_capita = EXCLUDED.ranking_pib_per_capita,
                                cluster = EXCLUDED.cluster,
                                perfil_cluster = EXCLUDED.perfil_cluster,
                                data_carga = CURRENT_TIMESTAMP
                            """
                        ),
                        self._row_params(row),
                    )

        self._save_processed("fato_ibge.csv", df_final)
        return df_final

    def run_pipeline(
        self,
        dados: Dict[str, Any],
        ano_populacao: int = 2024,
        ano_pib: int = 2023,
    ) -> Dict[str, pd.DataFrame]:
        """Executa o pipeline completo de carga."""
        logger.info("Iniciando carga no PostgreSQL.")
        self.create_tables()

        regioes_df = self.load_regions(dados["regioes"])
        estados_df = self.load_states(dados["estados"])
        fato_df = self.load_fact_data(
            dados["populacao"],
            dados["pib"],
            ano_populacao=ano_populacao,
            ano_pib=ano_pib,
        )

        logger.info("Carga concluída com sucesso.")
        return {
            "dim_regiao": regioes_df,
            "dim_estado": estados_df,
            "fato_ibge": fato_df,
        }

    def read_table(self, table_name: str) -> pd.DataFrame:
        """Lê uma tabela inteira do PostgreSQL para um DataFrame."""
        return pd.read_sql_table(table_name, self.engine)

    def read_query(self, query: str) -> pd.DataFrame:
        """Executa uma consulta SQL e retorna um DataFrame."""
        return pd.read_sql(text(query), self.engine)

    def read_indicadores_completos(self) -> pd.DataFrame:
        """Lê fato, estados e regiões em uma tabela analítica única."""
        return self.read_query(
            """
            SELECT
                f.id_fato,
                e.id_estado,
                e.sigla,
                e.nome_estado,
                r.id_regiao,
                r.sigla_regiao,
                r.nome_regiao,
                f.ano_populacao,
                f.ano_pib,
                f.populacao,
                f.pib_mil_reais,
                f.pib_per_capita,
                f.ranking_pib_per_capita,
                f.cluster,
                f.perfil_cluster,
                f.data_carga
            FROM fato_ibge f
            JOIN dim_estado e ON e.id_estado = f.id_estado
            LEFT JOIN dim_regiao r ON r.id_regiao = e.id_regiao
            ORDER BY f.ranking_pib_per_capita NULLS LAST, e.sigla
            """
        )
