"""Funções de tratamento de dados."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

JsonType = Union[List[Dict[str, Any]], Dict[str, Any]]


def adicionar_clusterizacao(df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """Adiciona ranking e clusters socioeconomicos a partir de PIB e população."""
    if df.empty:
        return df

    colunas = ["populacao", "pib_mil_reais", "pib_per_capita"]
    faltantes = [coluna for coluna in colunas if coluna not in df.columns]
    if faltantes:
        raise ValueError(f"Colunas ausentes para clusterização: {faltantes}")

    resultado = df.copy()
    resultado["ranking_pib_per_capita"] = (
        resultado["pib_per_capita"].rank(method="dense", ascending=False).astype(int)
    )

    features = resultado[colunas].apply(pd.to_numeric, errors="coerce")
    validos = features.dropna()
    if len(validos) < 2:
        resultado["cluster"] = 0
        resultado["perfil_cluster"] = "perfil_unico"
        return resultado

    total_clusters = min(n_clusters, len(validos))
    scaled = StandardScaler().fit_transform(validos)
    model = KMeans(n_clusters=total_clusters, random_state=42, n_init=10)
    clusters = pd.Series(model.fit_predict(scaled), index=validos.index)

    resultado["cluster"] = clusters
    resultado["cluster"] = resultado["cluster"].fillna(-1).astype(int)

    ordem = (
        resultado[resultado["cluster"] >= 0]
        .groupby("cluster")["pib_per_capita"]
        .mean()
        .sort_values()
        .reset_index()
        .reset_index()
    )
    ordem["perfil_cluster"] = ordem["index"].map(
        lambda posicao: f"perfil_{posicao + 1}_por_pib_per_capita"
    )
    labels = dict(zip(ordem["cluster"], ordem["perfil_cluster"]))
    resultado["perfil_cluster"] = resultado["cluster"].map(labels).fillna("sem_cluster")
    return resultado


class TratamentoIBGE:
    """Normaliza os dados brutos da API do IBGE."""

    def __init__(self, raw_path: str | None = None, processed_path: str | None = None):
        project_root = Path(__file__).resolve().parents[2]
        self.raw_path = Path(raw_path) if raw_path is not None else project_root / "data" / "raw"
        self.processed_path = (
            Path(processed_path)
            if processed_path is not None
            else project_root / "data" / "processed"
        )
        self.processed_path.mkdir(parents=True, exist_ok=True)

    def _to_dataframe(self, dados: JsonType) -> pd.DataFrame:
        if isinstance(dados, list):
            return pd.DataFrame(dados)
        if isinstance(dados, dict):
            return pd.DataFrame([dados])
        return pd.DataFrame()

    def _save_csv(self, df: pd.DataFrame, filename: str) -> Path:
        path = self.processed_path / filename
        df.to_csv(path, index=False, encoding="utf-8")
        return path

    def tratar_regioes(self, regioes: JsonType) -> pd.DataFrame:
        df = self._to_dataframe(regioes)

        if df.empty:
            return df

        colunas = {}
        for coluna in df.columns:
            nome = coluna.strip().lower()
            if nome == "id":
                colunas[coluna] = "id_regiao"
            elif nome == "sigla":
                colunas[coluna] = "sigla_regiao"
            elif nome == "nome":
                colunas[coluna] = "nome_regiao"

        df = df.rename(columns=colunas)

        colunas_esperadas = ["id_regiao", "sigla_regiao", "nome_regiao"]
        for coluna in colunas_esperadas:
            if coluna not in df.columns:
                df[coluna] = None

        df = df[colunas_esperadas].dropna(subset=["id_regiao", "nome_regiao"])
        df["id_regiao"] = pd.to_numeric(df["id_regiao"], errors="coerce")
        df = df.dropna(subset=["id_regiao"])
        df["id_regiao"] = df["id_regiao"].astype(int)

        df = df.drop_duplicates(subset=["id_regiao"]).reset_index(drop=True)
        return df

    def tratar_estados(self, estados: JsonType) -> pd.DataFrame:
        df = self._to_dataframe(estados)

        if df.empty:
            return df

        colunas = {}
        for coluna in df.columns:
            nome = coluna.strip().lower()
            if nome == "id":
                colunas[coluna] = "id_estado"
            elif nome == "sigla":
                colunas[coluna] = "sigla"
            elif nome == "nome":
                colunas[coluna] = "nome_estado"
            elif nome == "regiao":
                colunas[coluna] = "regiao"

        df = df.rename(columns=colunas)

        for coluna in ["id_estado", "sigla", "nome_estado", "regiao"]:
            if coluna not in df.columns:
                df[coluna] = None

        df["id_regiao"] = df["regiao"].apply(
            lambda valor: valor.get("id") if isinstance(valor, dict) else None
        )

        df = df[["id_estado", "sigla", "nome_estado", "id_regiao"]].copy()
        df["id_estado"] = pd.to_numeric(df["id_estado"], errors="coerce")
        df["id_regiao"] = pd.to_numeric(df["id_regiao"], errors="coerce")

        df = df.dropna(subset=["id_estado", "sigla", "nome_estado"])
        df["id_estado"] = df["id_estado"].astype(int)
        df["sigla"] = df["sigla"].astype(str).str.strip()
        df["nome_estado"] = df["nome_estado"].astype(str).str.strip()

        df["id_regiao"] = df["id_regiao"].astype("Int64")
        df = df.drop_duplicates(subset=["id_estado"]).reset_index(drop=True)
        return df

    def tratar_sidra(self, dados: JsonType, nome_valor: str) -> pd.DataFrame:
        """
        Converte o retorno do SIDRA em formato limpo.
        Espera colunas como:
        - D1C: código da UF
        - D1N: nome da UF
        - V: valor
        """
        df = self._to_dataframe(dados)

        if df.empty:
            return df

        df = df.rename(columns={coluna: coluna.strip() for coluna in df.columns})

        if "D1C" not in df.columns or "V" not in df.columns:
            return pd.DataFrame()

        base = df[["D1C", "D1N", "V"]].copy()
        base = base.rename(
            columns={
                "D1C": "codigo_estado",
                "D1N": "nome_estado",
                "V": nome_valor,
            }
        )

        base["codigo_estado"] = pd.to_numeric(base["codigo_estado"], errors="coerce")
        base[nome_valor] = (
            base[nome_valor]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        base[nome_valor] = pd.to_numeric(base[nome_valor], errors="coerce")

        base = base.dropna(subset=["codigo_estado", nome_valor])
        base["codigo_estado"] = base["codigo_estado"].astype(int)
        base["nome_estado"] = base["nome_estado"].astype(str).str.strip()

        base = base[["codigo_estado", "nome_estado", nome_valor]].reset_index(drop=True)
        return base

    def tratar_fato(
        self,
        populacao: JsonType,
        pib: JsonType,
        ano_populacao: int = 2024,
        ano_pib: int = 2023,
    ) -> pd.DataFrame:
        pop_df = self.tratar_sidra(populacao, "populacao")
        pib_df = self.tratar_sidra(pib, "pib_mil_reais")

        if pop_df.empty or pib_df.empty:
            return pd.DataFrame()

        df = pop_df.merge(
            pib_df[["codigo_estado", "pib_mil_reais"]],
            on="codigo_estado",
            how="inner",
            suffixes=("_pop", "_pib"),
        )

        df["pib_per_capita"] = (df["pib_mil_reais"] * 1000) / df["populacao"]
        df["ano_populacao"] = ano_populacao
        df["ano_pib"] = ano_pib

        df = df[
            [
                "codigo_estado",
                "nome_estado",
                "ano_populacao",
                "ano_pib",
                "populacao",
                "pib_mil_reais",
                "pib_per_capita",
            ]
        ].reset_index(drop=True)

        return df

    def pipeline_tratamento(
        self,
        dados: Dict[str, JsonType],
        ano_populacao: int = 2024,
        ano_pib: int = 2023,
        salvar_csv: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        regioes_df = self.tratar_regioes(dados.get("regioes", []))
        estados_df = self.tratar_estados(dados.get("estados", []))
        fato_df = self.tratar_fato(
            dados.get("populacao", []),
            dados.get("pib", []),
            ano_populacao=ano_populacao,
            ano_pib=ano_pib,
        )
        fato_df = adicionar_clusterizacao(fato_df)

        if salvar_csv:
            self._save_csv(regioes_df, "dim_regiao.csv")
            self._save_csv(estados_df, "dim_estado.csv")
            self._save_csv(fato_df, "fato_ibge.csv")

        return {
            "dim_regiao": regioes_df,
            "dim_estado": estados_df,
            "fato_ibge": fato_df,
        }
