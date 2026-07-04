#!/usr/bin/env bash
# Gera o workflow do bot a partir do template + .env e faz o deploy no n8n (via CLI, sem precisar de API key).
# Uso: ./deploy.sh   (rode de dentro da pasta n8n/, com o .env preenchido)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERRO: crie o arquivo .env (copie de .env.example) antes de rodar."
  exit 1
fi
set -a; source .env; set +a

: "${TELEGRAM_BOT_TOKEN:?defina no .env}"
: "${JENKINS_INSTANCES:?defina no .env (JSON em uma linha)}"
N8N_CONTAINER="${N8N_CONTAINER:-n8n}"
WORKFLOW_ID="${WORKFLOW_ID:-JenkinsTgBot0001}"
WORKFLOW_NAME="${WORKFLOW_NAME:-Jenkins Telegram Bot}"
POLL_SECONDS="${POLL_SECONDS:-30}"
ALLOWED_CHAT_IDS="${ALLOWED_CHAT_IDS:-}"

OUT=$(mktemp)
python3 - "$OUT" << 'PYEOF'
import json, os, sys

code = open("bot-code.template.js").read()
cfg = {
    "botToken": os.environ["TELEGRAM_BOT_TOKEN"],
    "instances": json.loads(os.environ["JENKINS_INSTANCES"]),
    "allowedChats": [int(c) for c in os.environ.get("ALLOWED_CHAT_IDS", "").replace(" ", "").split(",") if c],
}
code = code.replace("__CONFIG_JSON__", json.dumps(cfg, ensure_ascii=False))

wf = {
    "id": os.environ["WORKFLOW_ID"],
    "name": os.environ["WORKFLOW_NAME"],
    "nodes": [
        {
            "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": int(os.environ["POLL_SECONDS"])}]}},
            "id": "a1b2c3d4-0001-4000-8000-000000000001",
            "name": "Polling",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [0, 0],
        },
        {
            "parameters": {"jsCode": code},
            "id": "a1b2c3d4-0002-4000-8000-000000000002",
            "name": "Telegram <-> Jenkins",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [220, 0],
        },
    ],
    "connections": {"Polling": {"main": [[{"node": "Telegram <-> Jenkins", "type": "main", "index": 0}]]}},
    "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "none", "saveDataErrorExecution": "all"},
    "active": True,
}
open(sys.argv[1], "w").write(json.dumps(wf, ensure_ascii=False))
print("workflow gerado")
PYEOF

chmod 644 "$OUT"
docker cp "$OUT" "$N8N_CONTAINER":/tmp/jenkins-tg-bot.json
docker exec "$N8N_CONTAINER" n8n import:workflow --input=/tmp/jenkins-tg-bot.json
docker exec "$N8N_CONTAINER" n8n update:workflow --id="$WORKFLOW_ID" --active=true || true
echo "Reiniciando $N8N_CONTAINER para ativar..."
docker restart "$N8N_CONTAINER" > /dev/null
rm -f "$OUT"

echo "Registrando menu de comandos no Telegram..."
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setMyCommands" \
  -H "Content-Type: application/json" -d '{"commands":[
  {"command":"jobs","description":"Lista jobs com botões de ação"},
  {"command":"run","description":"Dispara build: /run job [PARAM=valor]"},
  {"command":"status","description":"Último build: /status job"},
  {"command":"log","description":"Console do último build: /log job"},
  {"command":"stop","description":"Aborta build em execução: /stop job"},
  {"command":"queue","description":"Fila de builds aguardando"},
  {"command":"watch","description":"Liga/desliga avisos de builds terminados"},
  {"command":"jenkins","description":"Status das instâncias Jenkins"},
  {"command":"chatid","description":"Mostra o id deste chat"},
  {"command":"help","description":"Ajuda"}]}' > /dev/null

echo
echo "✅ Deploy concluído. Workflow '$WORKFLOW_NAME' (id $WORKFLOW_ID) ativo no container $N8N_CONTAINER."
