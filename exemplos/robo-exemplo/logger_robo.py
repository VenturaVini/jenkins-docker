"""Logger padrão dos robôs: linhas amigáveis, pensadas para quem não programa.

Cada evento vira uma linha limpa, com emoji e sem jargão:
  🚀 Robô iniciado · python: 3.12.4
  🌐 Consulta http · url: https://... · status: 200 · duração: 0.1s
  ✅ Robô finalizado · status: sucesso · duração: 2s

Variáveis de ambiente (todas opcionais):
  LOG_TIMESTAMP=1  volta a mostrar data/hora no início de cada linha
  LOG_JSON=1       emite também uma linha JSON por evento (jq, Loki, Elastic)
  LOG_HUMANO=0     desliga a linha amigável (só JSON)
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

# Emoji escolhido pela palavra-chave presente no nome do evento (primeira que casar).
_EMOJI_EVENTO = [
    ("inicia", "🚀"),
    ("finaliz", "✅"),
    ("sucesso", "✅"),
    ("salv", "💾"),
    ("consulta", "🌐"),
    ("http", "🌐"),
    ("pagina", "📄"),
    ("video", "🎬"),
    ("busca", "🔍"),
    ("download", "⬇️"),
    ("upload", "⬆️"),
    ("esper", "⏳"),
    ("visit", "👀"),
]
_EMOJI_NIVEL = {"DEBUG": "🔧", "INFO": "🔹", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}


def _emoji(evento: str, nivel: str) -> str:
    if nivel in ("ERROR", "CRITICAL", "WARNING"):
        return _EMOJI_NIVEL[nivel]
    texto = evento.lower()
    for chave, emoji in _EMOJI_EVENTO:
        if chave in texto:
            return emoji
    return _EMOJI_NIVEL.get(nivel, "🔹")


def _humaniza(texto: str) -> str:
    """robo_iniciado -> Robô iniciado (troca _ por espaço e capitaliza)."""
    bonito = texto.replace("_", " ").strip().capitalize()
    return bonito.replace("Robo ", "Robô ").replace(" robo", " robô")


def _valor_amigavel(nome: str, valor):
    """Durações em ms viram segundos legíveis; o resto passa direto."""
    if nome.endswith("_ms") and isinstance(valor, (int, float)):
        segundos = valor / 1000
        if segundos >= 60:
            return "duração", f"{int(segundos // 60)}m{round(segundos % 60)}s"
        if segundos >= 1:
            return "duração", f"{round(segundos, 1)}s"
        return "duração", "menos de 1s"
    return nome.replace("_", " "), valor


class FormatterAmigavel(logging.Formatter):
    """Linha amigável (padrão) e/ou linha JSON estruturada por evento."""

    def __init__(self, robo: str):
        super().__init__()
        self.robo = robo
        self.humano = os.environ.get("LOG_HUMANO", "1") != "0"
        self.json = os.environ.get("LOG_JSON", "0") == "1"
        self.timestamp = os.environ.get("LOG_TIMESTAMP", "0") == "1"

    def format(self, record: logging.LogRecord) -> str:
        agora = datetime.datetime.now(TZ)
        campos = getattr(record, "campos", None) or {}
        saidas = []

        if self.humano:
            evento = record.getMessage()
            partes = [f"{_emoji(evento, record.levelname)} {_humaniza(evento)}"]
            for k, v in campos.items():
                nome, valor = _valor_amigavel(k, v)
                partes.append(f"{nome}: {valor}")
            linha = " · ".join(partes)
            if self.timestamp:
                linha = f"[{agora:%d/%m/%Y %H:%M:%S}] {linha}"
            saidas.append(linha)
            if record.exc_info:
                saidas.append(f"💥 O que deu errado (detalhe técnico):")
                saidas.append(self.formatException(record.exc_info))

        if self.json:
            registro = {
                "timestamp": agora.isoformat(),
                "nivel": record.levelname,
                "robo": self.robo,
                "run_id": RUN_ID,
                "evento": record.getMessage(),
            }
            registro.update(campos)
            if record.exc_info:
                registro["excecao"] = self.formatException(record.exc_info)
            saidas.append(json.dumps(registro, ensure_ascii=False))

        return "\n".join(saidas)


def criar_logger(robo: str) -> logging.Logger:
    logger = logging.getLogger(robo)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatterAmigavel(robo))
    logger.addHandler(handler)
    return logger


def log_evento(logger: logging.Logger, evento: str, nivel: str = "info", **campos) -> None:
    """Atalho: log_evento(log, "video_encontrado", titulo="...", canal="...")."""
    getattr(logger, nivel)(evento, extra={"campos": campos})
