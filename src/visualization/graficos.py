""" Funções para criação de gráficos """

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style('whitegrid')


def _finalizar_grafico(output_path=None, show=True):
    """Salva e/ou exibe a figura atual."""
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()

""" Gráficos de população """

def grafico_populacao_estados(df, output_path=None, show=True):
    """ Mostra a população dos estados em milhões. """

    estados = (
        df[['sigla', 'populacao']]
        .sort_values('populacao', ascending=True)
        .copy()
    )

    # converte para milhões
    estados['populacao_milhoes'] = estados['populacao'] / 1_000_000

    plt.figure(figsize=(12, 10))

    sns.barplot(
        data=estados,
        y='sigla',
        x='populacao_milhoes'
    )

    plt.title('População por Estado')
    plt.xlabel('População (milhões)')
    plt.ylabel('Estado')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)

def grafico_populacao_regiao(df, output_path=None, show=True):
    """ População total por região em milhões. """

    regioes = (
        df.groupby('nome_regiao')['populacao']
        .sum()
        .reset_index()
        .sort_values('populacao', ascending=False)
    )

    regioes['populacao_milhoes'] = (
        regioes['populacao'] / 1_000_000
    ).round(1)

    plt.figure(figsize=(10, 6))

    sns.barplot(
        data=regioes,
        x='nome_regiao',
        y='populacao_milhoes'
    )

    plt.title('População por Região')
    plt.xlabel('Região')
    plt.ylabel('População (milhões)')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)

def grafico_percentual_populacao_regiao(df, output_path=None, show=True):
    """ Participação percentual da população por região. """

    regioes = (
        df.groupby('nome_regiao')['populacao']
        .sum()
        .reset_index()
    )

    total = regioes['populacao'].sum()

    regioes['percentual'] = (
        regioes['populacao'] / total * 100
    ).round(1)

    plt.figure(figsize=(8, 8))

    plt.pie(
        regioes['percentual'],
        labels=regioes['nome_regiao'],
        autopct='%1.1f%%'
    )

    plt.title('Participação Percentual da População por Região')

    _finalizar_grafico(output_path, show)

""" Gráficos de PIB """

def grafico_pib_estados(df, output_path=None, show=True):
    """ PIB dos estados em milhões de reais. """

    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd

    estados = df[['sigla', 'pib_mil_reais']].copy()

    # garante que a coluna seja numérica
    estados['pib_mil_reais'] = pd.to_numeric(
        estados['pib_mil_reais'],
        errors='coerce'
    )

    # ordena os estados
    estados = estados.sort_values(
        'pib_mil_reais',
        ascending=True
    )

    # converte para milhões de reais
    estados['pib_milhoes'] = (
        estados['pib_mil_reais'] / 1_000
    ).round(0)

    plt.figure(figsize=(12, 10))

    sns.barplot(
        data=estados,
        y='sigla',
        x='pib_milhoes'
    )

    plt.title('PIB por Estado')
    plt.xlabel('PIB (milhões de reais)')
    plt.ylabel('Estado')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)

def grafico_pib_medio_regiao(df, output_path=None, show=True):
    """ PIB médio por região. """

    regioes = (
        df.groupby('nome_regiao')['pib_mil_reais']
        .mean()
        .reset_index()
        .sort_values('pib_mil_reais', ascending=False)
    )

    regioes['pib_medio_bilhoes'] = (
        regioes['pib_mil_reais'] / 1_000_000
    ).round(1)

    plt.figure(figsize=(10, 6))

    sns.barplot(
        data=regioes,
        x='nome_regiao',
        y='pib_medio_bilhoes'
    )

    plt.title('PIB Médio por Região')
    plt.xlabel('Região')
    plt.ylabel('PIB Médio (bilhões)')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)


def grafico_ranking_pib_per_capita(df, output_path=None, show=True):
    """Ranking de PIB per capita por estado."""

    dados = (
        df[['sigla', 'pib_per_capita', 'nome_regiao']]
        .copy()
        .sort_values('pib_per_capita', ascending=True)
    )

    plt.figure(figsize=(12, 10))

    sns.barplot(
        data=dados,
        y='sigla',
        x='pib_per_capita',
        hue='nome_regiao',
        dodge=False
    )

    plt.title('Ranking de PIB per capita por Estado')
    plt.xlabel('PIB per capita (R$)')
    plt.ylabel('Estado')
    plt.legend(title='Região', loc='lower right')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)

def grafico_relacao_populacao_pib(df, output_path=None, show=True):
    """ Relação entre população e PIB. """

    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd

    dados = df.copy()

    # garante valores numéricos
    dados['pib_mil_reais'] = pd.to_numeric(
        dados['pib_mil_reais'],
        errors='coerce'
    )

    dados['populacao'] = pd.to_numeric(
        dados['populacao'],
        errors='coerce'
    )

    # conversões
    dados['populacao_milhoes'] = (
        dados['populacao'] / 1_000_000
    ).round(1)

    dados['pib_milhoes'] = (
        dados['pib_mil_reais'] / 1_000
    ).round(0)

    plt.figure(figsize=(12, 8))

    sns.scatterplot(
        data=dados,
        x='populacao_milhoes',
        y='pib_milhoes',
        hue='nome_regiao',
        s=120
    )

    plt.title('Relação entre População e PIB')
    plt.xlabel('População (milhões)')
    plt.ylabel('PIB (milhões de reais)')

    plt.tight_layout()
    _finalizar_grafico(output_path, show)


def gerar_todos_graficos(df, output_dir="data/exports", show=False):
    """Gera os gráficos principais e salva em PNG."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    graficos = {
        "ranking_pib_per_capita.png": grafico_ranking_pib_per_capita,
        "populacao_estados.png": grafico_populacao_estados,
        "populacao_regiao.png": grafico_populacao_regiao,
        "percentual_populacao_regiao.png": grafico_percentual_populacao_regiao,
        "pib_estados.png": grafico_pib_estados,
        "pib_medio_regiao.png": grafico_pib_medio_regiao,
        "relacao_populacao_pib.png": grafico_relacao_populacao_pib,
    }

    caminhos = []
    for filename, funcao in graficos.items():
        path = output / filename
        funcao(df, output_path=path, show=show)
        caminhos.append(path)

    return caminhos
