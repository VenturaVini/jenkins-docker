"""Robô de web scraping com logs estruturados (JSON lines).

Raspa citações de https://quotes.toscrape.com (site público feito para
prática de scraping) e salva o resultado em saida/quotes.json.

Cada linha de log é um JSON com timestamp, nível, evento e campos extras,
pronto para ser ingerido por Loki/Elastic ou filtrado com jq.
"""
import datetime
import json
import logging
import sys
import time
import uuid
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROBO = "robo-scraper"
BASE_URL = "https://quotes.toscrape.com"
MAX_PAGINAS = 3
SAIDA = Path(__file__).parent / "saida" / "quotes.json"

RUN_ID = uuid.uuid4().hex[:12]


class JsonFormatter(logging.Formatter):
    """Formata cada registro de log como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        linha = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "nivel": record.levelname,
            "robo": ROBO,
            "run_id": RUN_ID,
            "evento": record.getMessage(),
        }
        extras = getattr(record, "campos", None)
        if extras:
            linha.update(extras)
        if record.exc_info:
            linha["excecao"] = self.formatException(record.exc_info)
        return json.dumps(linha, ensure_ascii=False)


def configurar_logger() -> logging.Logger:
    logger = logging.getLogger(ROBO)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


log = configurar_logger()


def raspar_pagina(sessao: requests.Session, pagina: int) -> tuple[list[dict], bool]:
    """Raspa uma página de citações. Retorna (citações, existe_próxima)."""
    url = f"{BASE_URL}/page/{pagina}/"
    inicio = time.monotonic()
    resposta = sessao.get(url, timeout=15)
    duracao_ms = round((time.monotonic() - inicio) * 1000)
    log.info(
        "http_request",
        extra={"campos": {"url": url, "status": resposta.status_code, "duracao_ms": duracao_ms}},
    )
    resposta.raise_for_status()

    sopa = BeautifulSoup(resposta.text, "html.parser")
    citacoes = [
        {
            "texto": bloco.select_one(".text").get_text(strip=True),
            "autor": bloco.select_one(".author").get_text(strip=True),
            "tags": [tag.get_text(strip=True) for tag in bloco.select(".tag")],
        }
        for bloco in sopa.select(".quote")
    ]
    tem_proxima = sopa.select_one("li.next") is not None
    log.info(
        "pagina_raspada",
        extra={"campos": {"pagina": pagina, "citacoes": len(citacoes), "tem_proxima": tem_proxima}},
    )
    return citacoes, tem_proxima


def main() -> None:
    inicio = time.monotonic()
    log.info("robo_iniciado", extra={"campos": {"base_url": BASE_URL, "max_paginas": MAX_PAGINAS}})

    citacoes: list[dict] = []
    try:
        with requests.Session() as sessao:
            sessao.headers["User-Agent"] = f"{ROBO}/1.0 (jenkins)"
            for pagina in range(1, MAX_PAGINAS + 1):
                novas, tem_proxima = raspar_pagina(sessao, pagina)
                citacoes.extend(novas)
                if not tem_proxima:
                    break

        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        SAIDA.write_text(json.dumps(citacoes, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("resultado_salvo", extra={"campos": {"arquivo": str(SAIDA), "total": len(citacoes)}})
    except Exception:
        log.error(
            "robo_falhou",
            extra={"campos": {"duracao_ms": round((time.monotonic() - inicio) * 1000)}},
            exc_info=True,
        )
        sys.exit(1)

    log.info(
        "robo_finalizado",
        extra={
            "campos": {
                "total_citacoes": len(citacoes),
                "duracao_ms": round((time.monotonic() - inicio) * 1000),
                "status": "sucesso",
            }
        },
    )


if __name__ == "__main__":
    main()
