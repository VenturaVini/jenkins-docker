"""Logger padrão dos robôs: linha legível com data/hora local + linha JSON estruturada.

Cada evento sai em dois formatos no mesmo stdout:
  [03/07/2026 22:41:07] INFO  ▶ http_request  url=... status=200 duracao_ms=145
  {"timestamp": "...", "data_hora": "03/07/2026 22:41:07", "nivel": "INFO", ...}

A linha legível é para acompanhar o build no Jenkins; a JSON é para máquinas
(jq, Loki, Elastic). Desligue uma delas com LOG_HUMANO=0 ou LOG_JSON=0.
"""
import datetime
import json
import logging
import os
import sys
import uuid
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
RUN_ID = uuid.uuid4().hex[:12]

_EMOJI = {"DEBUG": "·", "INFO": "▶", "WARNING": "⚠", "ERROR": "✖", "CRITICAL": "✖✖"}


class FormatterDuplo(logging.Formatter):
    """Emite a linha legível e a linha JSON para cada registro."""

    def __init__(self, robo: str):
        super().__init__()
        self.robo = robo
        self.humano = os.environ.get("LOG_HUMANO", "1") != "0"
        self.json = os.environ.get("LOG_JSON", "1") != "0"

    def format(self, record: logging.LogRecord) -> str:
        agora = datetime.datetime.now(TZ)
        campos = getattr(record, "campos", None) or {}
        saidas = []

        if self.humano:
            detalhes = "  ".join(f"{k}={v}" for k, v in campos.items())
            emoji = _EMOJI.get(record.levelname, "▶")
            linha = f"[{agora:%d/%m/%Y %H:%M:%S}] {record.levelname:<7} {emoji} {record.getMessage()}"
            if detalhes:
                linha += f"  {detalhes}"
            saidas.append(linha)

        if self.json:
            registro = {
                "timestamp": agora.isoformat(),
                "data_hora": f"{agora:%d/%m/%Y %H:%M:%S}",
                "nivel": record.levelname,
                "robo": self.robo,
                "run_id": RUN_ID,
                "evento": record.getMessage(),
            }
            registro.update(campos)
            if record.exc_info:
                registro["excecao"] = self.formatException(record.exc_info)
            saidas.append(json.dumps(registro, ensure_ascii=False))

        if record.exc_info and self.humano and not self.json:
            saidas.append(self.formatException(record.exc_info))
        return "\n".join(saidas)


def criar_logger(robo: str) -> logging.Logger:
    logger = logging.getLogger(robo)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatterDuplo(robo))
    logger.addHandler(handler)
    return logger


def log_evento(logger: logging.Logger, evento: str, nivel: str = "info", **campos) -> None:
    """Atalho: log_evento(log, "video_encontrado", titulo="...", canal="...")."""
    getattr(logger, nivel)(evento, extra={"campos": campos})
