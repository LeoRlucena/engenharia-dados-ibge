"""Módulo de extração de dados da API do IBGE."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


JsonType = Union[Dict[str, Any], List[Any]]


class IBGEAPIClient:
    """Cliente para consumir dados da API do IBGE."""

    BASE_URL_SIDRA = "https://apisidra.ibge.gov.br"
    BASE_URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"

    def __init__(self, raw_data_path: Optional[str] = None):
        if raw_data_path is None:
            project_root = Path(__file__).resolve().parents[2]
            self.raw_data_path = project_root / "data" / "raw"
        else:
            self.raw_data_path = Path(raw_data_path)
        self.raw_data_path.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _save_raw_data(self, filename: str, data: JsonType) -> Path:
        filepath = self.raw_data_path / filename
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        logger.info("Dados brutos salvos em: %s", filepath)
        return filepath

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> JsonType:
        try:
            logger.info("Requisição GET: %s", url)
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            logger.info("Resposta recebida com sucesso (status %s)", response.status_code)
            return response.json()
        except requests.RequestException as exc:
            logger.error("Erro ao fazer requisição para %s: %s", url, exc)
            raise

    def get_populacao(self, ano: int = 2024) -> JsonType:
        """
        Obtém dados de população por estado.
        """
        url = f"{self.BASE_URL_SIDRA}/values/t/6579/n3/all/v/9324/p/{ano}"
        params = {"formato": "json"}
        data = self._make_request(url, params)
        self._save_raw_data(f"populacao_{ano}_{self._timestamp()}.json", data)
        return data

    def get_pib(self, ano: int = 2023) -> JsonType:
        """
        Obtém dados de PIB por estado.
        """
        url = f"{self.BASE_URL_SIDRA}/values/t/5938/n3/all/v/37/p/{ano}"
        params = {"formato": "json"}
        data = self._make_request(url, params)
        self._save_raw_data(f"pib_{ano}_{self._timestamp()}.json", data)
        return data

    def get_estados(self) -> JsonType:
        """
        Obtém a lista de estados brasileiros.
        """
        url = f"{self.BASE_URL_LOCALIDADES}/estados"
        data = self._make_request(url)
        self._save_raw_data(f"estados_{self._timestamp()}.json", data)
        return data

    def get_regioes(self) -> JsonType:
        """
        Obtém a lista de regiões brasileiras.
        """
        url = f"{self.BASE_URL_LOCALIDADES}/regioes"
        data = self._make_request(url)
        self._save_raw_data(f"regioes_{self._timestamp()}.json", data)
        return data

    def extract_all(self, ano_populacao: int = 2024, ano_pib: int = 2023) -> Dict[str, Any]:
        """
        Extrai todos os dados necessários da API do IBGE.
        """
        logger.info("=== Iniciando extração de dados ===")

        try:
            populacao = self.get_populacao(ano_populacao)
            pib = self.get_pib(ano_pib)
            estados = self.get_estados()
            regioes = self.get_regioes()

            resultado = {
                "populacao": populacao,
                "pib": pib,
                "estados": estados,
                "regioes": regioes,
                "metadata": {
                    "executado_em": datetime.now().isoformat(),
                    "ano_populacao": ano_populacao,
                    "ano_pib": ano_pib,
                },
            }

            self._save_raw_data(f"extract_all_{self._timestamp()}.json", resultado)
            logger.info("=== Extração concluída com sucesso ===")
            return resultado

        except Exception as exc:
            logger.error("Erro durante extração: %s", exc)
            raise


def main() -> None:
    client = IBGEAPIClient()
    dados = client.extract_all()
    print(json.dumps(dados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()