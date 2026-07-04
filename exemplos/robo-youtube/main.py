"""Robô YouTube: busca vídeos de um tema (aleatório ou configurado) e lista os primeiros.

Fluxo:
  1. Lê config.json (quantidade de vídeos, tema, intervalo). Sem arquivo, usa padrões.
  2. Sorteia um tema (se nenhum foi fixado) e busca no YouTube.
  3. Visita os vídeos UM POR UM, com um timer entre cada — dá para acompanhar
     o progresso ao vivo no log do Jenkins.
  4. Salva a lista em saida/videos.json.

Não usa API key: raspa a página de busca e usa o endpoint público oEmbed.
"""
import json
import random
import sys
import time
import urllib.parse
from pathlib import Path

import requests

from logger_robo import criar_logger, log_evento

ROBO = "robo-youtube"
PASTA = Path(__file__).parent
CONFIG = PASTA / "config.json"
SAIDA = PASTA / "saida" / "videos.json"

PADROES = {
    "tema": "",  # vazio = sorteia um de temas_aleatorios
    "quantidade": 6,
    "intervalo_segundos": 5,
    "temas_aleatorios": [
        "python automação",
        "docker tutorial",
        "jenkins pipeline",
        "n8n workflow",
        "web scraping",
        "linux servidor",
        "raspberry pi projetos",
        "engenharia de dados",
    ],
}

log = criar_logger(ROBO)


def carregar_config() -> dict:
    """config.json manda; o que faltar (ou se o arquivo não existir) cai nos padrões."""
    config = dict(PADROES)
    if CONFIG.exists():
        config.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        log_evento(log, "config_carregada", arquivo=str(CONFIG), quantidade=config["quantidade"])
    else:
        log_evento(log, "config_padrao", nivel="warning", motivo="config.json não encontrado, usando padrões")
    return config


def buscar_video_ids(sessao: requests.Session, tema: str, quantidade: int) -> list[str]:
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(tema)
    inicio = time.monotonic()
    resposta = sessao.get(url, timeout=20)
    duracao_ms = round((time.monotonic() - inicio) * 1000)
    log_evento(log, "busca_youtube", tema=tema, status=resposta.status_code, duracao_ms=duracao_ms)
    resposta.raise_for_status()

    ids: list[str] = []
    for pedaco in resposta.text.split('"videoId":"')[1:]:
        video_id = pedaco[:11]
        if len(video_id) == 11 and video_id not in ids:
            ids.append(video_id)
        if len(ids) >= quantidade:
            break
    return ids


def detalhar_video(sessao: requests.Session, video_id: str) -> dict:
    url_video = f"https://www.youtube.com/watch?v={video_id}"
    oembed = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url_video)
    resposta = sessao.get(oembed, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()
    return {"video_id": video_id, "titulo": dados["title"], "canal": dados["author_name"], "url": url_video}


def main() -> None:
    inicio = time.monotonic()
    config = carregar_config()
    tema = config["tema"] or random.choice(config["temas_aleatorios"])
    quantidade = int(config["quantidade"])
    intervalo = float(config["intervalo_segundos"])
    log_evento(log, "robo_iniciado", tema=tema, quantidade=quantidade, intervalo_segundos=intervalo)

    videos: list[dict] = []
    try:
        with requests.Session() as sessao:
            sessao.headers["User-Agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            )
            sessao.cookies.set("CONSENT", "YES+1", domain=".youtube.com")

            ids = buscar_video_ids(sessao, tema, quantidade)
            if not ids:
                raise RuntimeError(f"nenhum vídeo encontrado para o tema '{tema}'")
            log_evento(log, "resultados_encontrados", total=len(ids))

            for posicao, video_id in enumerate(ids, start=1):
                video = detalhar_video(sessao, video_id)
                video["posicao"] = posicao
                videos.append(video)
                log_evento(
                    log,
                    "video_encontrado",
                    posicao=f"{posicao}/{len(ids)}",
                    titulo=video["titulo"],
                    canal=video["canal"],
                    url=video["url"],
                )
                if posicao < len(ids):
                    time.sleep(intervalo)  # timer: um por um, para acompanhar ao vivo

        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        SAIDA.write_text(
            json.dumps({"tema": tema, "videos": videos}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log_evento(log, "resultado_salvo", arquivo=str(SAIDA), total=len(videos))
    except Exception:
        log.error(
            "robo_falhou",
            extra={"campos": {"duracao_ms": round((time.monotonic() - inicio) * 1000)}},
            exc_info=True,
        )
        sys.exit(1)

    log_evento(
        log,
        "robo_finalizado",
        status="sucesso",
        tema=tema,
        total_videos=len(videos),
        duracao_ms=round((time.monotonic() - inicio) * 1000),
    )


if __name__ == "__main__":
    main()
