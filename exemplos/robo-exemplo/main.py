"""Robô de exemplo: prova que o Jenkins consegue rodar Python em container.

Logs no padrão dos robôs: linhas amigáveis com emoji, pensadas para
qualquer pessoa acompanhar no Jenkins (ver logger_robo.py).
"""
import platform
import sys
import time

import requests

from logger_robo import criar_logger, log_evento

ROBO = "robo-exemplo"
log = criar_logger(ROBO)


def main() -> None:
    inicio = time.monotonic()
    log_evento(log, "robo_iniciado", python=platform.python_version(), plataforma=platform.machine())

    try:
        resposta = requests.get("https://api.github.com/zen", timeout=10)
        resposta.raise_for_status()
        log_evento(log, "consulta_http", url="https://api.github.com/zen", status=resposta.status_code, frase=resposta.text)
    except Exception:
        log.error(
            "robo_falhou",
            extra={"campos": {"duracao_ms": round((time.monotonic() - inicio) * 1000)}},
            exc_info=True,
        )
        sys.exit(1)

    log_evento(log, "robo_finalizado", status="sucesso", duracao_ms=round((time.monotonic() - inicio) * 1000))


if __name__ == "__main__":
    main()
