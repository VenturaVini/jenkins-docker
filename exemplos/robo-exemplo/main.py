"""Robô de exemplo: prova que o Jenkins consegue rodar Python em container."""
import datetime
import platform

import requests


def main() -> None:
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(f"[robo-exemplo] Iniciado em {agora}")
    print(f"[robo-exemplo] Python {platform.python_version()} rodando em container")

    resposta = requests.get("https://api.github.com/zen", timeout=10)
    print(f"[robo-exemplo] Consulta HTTP ok (status {resposta.status_code}): {resposta.text}")

    print("[robo-exemplo] Finalizado com sucesso!")


if __name__ == "__main__":
    main()
