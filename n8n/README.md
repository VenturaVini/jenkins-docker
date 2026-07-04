# 🤖 Bot Telegram ↔ Jenkins (via n8n)

Bot de Telegram que lista, dispara e monitora jobs de um ou mais Jenkins — rodando como um workflow do n8n, sem servidor extra.

## Comandos

| Comando | Ação |
|---|---|
| `/jobs` | Lista os jobs com **botões inline** (▶️ rodar, 📊 status, 📜 log) — sem digitar nome |
| `/run job [PARAM=valor ...]` | Dispara build (com parâmetros opcionais) e **avisa quando terminar** |
| `/status job` | Último build: resultado, duração, % de progresso se em execução |
| `/log job` | Últimas linhas do console do último build |
| `/stop job` | Aborta o build em execução |
| `/queue` | Fila de builds aguardando |
| `/watch` | Liga/desliga avisos automáticos de **todo** build que terminar (com tail do log em caso de falha) |
| `/jenkins` | Status de cada instância Jenkins configurada |
| `/chatid` | Id do chat (para preencher `ALLOWED_CHAT_IDS`) |

## Arquitetura

- **Polling, não webhook**: o Telegram exige HTTPS para webhooks; como o n8n roda em HTTP, o workflow usa um Schedule Trigger (a cada `POLL_SECONDS`) + long-polling do `getUpdates`. Resposta típica em poucos segundos.
- **Um nó Code** faz tudo: lê comandos, fala com o(s) Jenkins e responde. O estado (offset do Telegram, builds monitorados, chats com watch) fica no *static data* do workflow.
- O n8n alcança o Jenkins pela **rede docker** (`http://jenkins:8080`) — os containers precisam estar na mesma rede.

## Como subir (nesta ou em outra máquina)

1. Crie um bot no Telegram com o [@BotFather](https://t.me/BotFather) e copie o token.
2. No Jenkins: *usuário → Configurações → API Token → gerar*. Copie o token.
3. Garanta que o container do n8n enxerga o do Jenkins:
   ```bash
   docker network connect <rede_do_n8n> <container_jenkins>   # se ainda não estiverem juntos
   ```
4. Configure e faça o deploy:
   ```bash
   cd n8n
   cp .env.example .env   # preencha TELEGRAM_BOT_TOKEN e JENKINS_INSTANCES
   ./deploy.sh
   ```
5. Adicione o bot ao seu grupo, mande `/chatid`, coloque o id em `ALLOWED_CHAT_IDS` no `.env` e rode `./deploy.sh` de novo (sem isso, **qualquer pessoa** que achar o bot pode disparar builds).

## Vários Jenkins

Acrescente objetos ao array `JENKINS_INSTANCES` no `.env`:

```
JENKINS_INSTANCES=[{"name":"principal","url":"http://jenkins:8080","user":"admin","token":"xxx"},{"name":"cliente-b","url":"http://jenkins-b:8080","user":"admin","token":"yyy"}]
```

O bot mostra os jobs agrupados por instância e resolve automaticamente em qual Jenkins cada job está quando você digita `/run nome-do-job`.

## Atualizar o bot

Edite `bot-code.template.js` (ou o `.env`) e rode `./deploy.sh` — ele reimporta o workflow com o mesmo id (não duplica) e reinicia o n8n para ativar.
