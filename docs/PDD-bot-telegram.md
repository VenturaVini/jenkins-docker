# PDD — Documento de Definição de Processo

**Processo:** Operação de robôs Jenkins via Telegram (bot no n8n)
**Versão:** 1.0 — 03/07/2026
**Responsável:** Vinícius Ventura (vini.ventura98@gmail.com)

---

## 1. Objetivo

Permitir operar o Jenkins pelo celular, sem abrir a interface web: listar jobs, disparar builds (inclusive com parâmetros), acompanhar status, ler logs e receber avisos automáticos quando builds terminam — tudo em um grupo do Telegram. O bot roda como um workflow do n8n já existente no servidor: nenhum serviço novo, nenhuma porta nova exposta.

## 2. Escopo

| Item | Descrição |
|---|---|
| Canal | Grupo (ou chat) do Telegram com o bot **@JENKINS_VINI_bot** |
| Motor | Workflow "Jenkins Telegram Bot" no n8n (Schedule Trigger + nó Code) |
| Alvo | Um ou mais Jenkins, configurados em `JENKINS_INSTANCES` no `.env` |
| Comandos | `/jobs`, `/run`, `/status`, `/log`, `/stop`, `/queue`, `/watch`, `/jenkins`, `/chatid`, `/help` |
| Fora de escopo | Criação/edição de jobs pelo bot; webhook HTTPS do Telegram (ver §3); aprovações multiusuário |

## 3. Arquitetura

```
┌───────────────────────── Servidor (Docker host) ─────────────────────────┐
│                                                                          │
│   rede n8n_app_network                                                   │
│  ┌───────────────────────────────┐        ┌─────────────┐                │
│  │  n8n (workflow do bot)        │  REST   │   Jenkins   │                │
│  │  ⏱ a cada 30s:               ├────────▶│  :3878→8080 │ (1..N          │
│  │   1. getUpdates (long-poll)   │  API    └─────────────┘  instâncias)  │
│  │   2. executa comandos         │                                        │
│  │   3. monitora builds (watch)  │                                        │
│  └───────────────┬───────────────┘                                        │
│                  │ HTTPS (saída)                                          │
└──────────────────┼────────────────────────────────────────────────────────┘
                   ▼
          api.telegram.org  ◀────────  📱 grupo no Telegram
```

Decisões técnicas:

- **Polling em vez de webhook**: o Telegram só entrega webhooks via HTTPS e o n8n do servidor roda em HTTP. O workflow usa Schedule Trigger (30s) + `getUpdates` com long-poll de 15s — na prática a resposta chega em poucos segundos, sem expor porta nem certificado.
- **Um único nó Code**: comandos, chamadas ao Jenkins e respostas ficam em um só lugar (`n8n/bot-code.template.js`), versionado no git. O workflow no n8n é **artefato gerado** — a fonte da verdade é o template + `.env`.
- **Estado no static data do workflow**: offset do Telegram, chats com `/watch` ligado, builds aguardando aviso e último build visto de cada job sobrevivem a reinícios do n8n (ficam no Postgres).
- **Autenticação no Jenkins por API token** (usuário + token, sem crumb), um por instância.
- **Botões inline** (callback queries) para agir sem digitar nome de job; `callback_data` carrega o índice da instância + nome do job.

## 4. Fluxos do processo

### 4.1 Disparar um robô pelo celular

1. Usuário manda `/jobs` no grupo.
2. Bot responde a lista com o status de cada job e botões `▶️ rodar / 📊 status / 📜 log`.
3. Usuário toca `▶️ rodar` (ou digita `/run robo-scraper`, com `PARAM=valor` se o job for parametrizado).
4. Bot dispara o build via API e registra o chat como interessado.
5. Quando o build termina, o bot avisa no mesmo chat: resultado, duração e, em caso de falha, as últimas linhas do console.

### 4.2 Monitoramento contínuo (`/watch`)

1. Usuário manda `/watch` no grupo → modo monitor ligado para aquele chat.
2. A cada ciclo o bot compara o último build de cada job (em todas as instâncias) com o último visto.
3. Todo build concluído gera aviso — inclusive os disparados por cron, webhook ou pela interface web.
4. `/watch` de novo desliga.

### 4.3 Vários Jenkins

1. Cada instância entra como um objeto em `JENKINS_INSTANCES` no `.env` (nome, URL vista de dentro do n8n, usuário, API token).
2. `/jobs` agrupa por instância; comandos digitados procuram o job em todas elas, na ordem.
3. Requisito de rede: o container do n8n precisa alcançar o Jenkins da instância (mesma rede docker ou URL externa).

## 5. Ambiente e acesso

| Campo | Valor |
|---|---|
| Bot | @JENKINS_VINI_bot (token no `n8n/.env`, gitignorado) |
| Workflow n8n | "Jenkins Telegram Bot", id `4EMFFfZ7b7CAax2M` |
| Jenkins "principal" | `http://jenkins:8080` (interno) = http://209.50.241.178:3878/ |
| Autorização de chats | `ALLOWED_CHAT_IDS` no `n8n/.env` — **preencher antes de divulgar o bot**; vazio = qualquer chat comanda builds |

## 6. Operação e manutenção

| Tarefa | Como |
|---|---|
| Alterar comportamento do bot | editar `n8n/bot-code.template.js` e rodar `n8n/deploy.sh` |
| Alterar tokens/instâncias/chats | editar `n8n/.env` e rodar `n8n/deploy.sh` |
| Ver falhas do workflow | n8n → Executions (só erros são gravados) ou `docker logs n8n-worker` |
| Restringir acesso | `/chatid` no grupo → id em `ALLOWED_CHAT_IDS` → `deploy.sh` |
| Trocar o bot | novo token no @BotFather → `TELEGRAM_BOT_TOKEN` no `.env` → `deploy.sh` |

> Não chame `getUpdates` do bot manualmente (curl etc.) com o workflow ativo: o Telegram só entrega cada mensagem a um consumidor, e a chamada manual "rouba" comandos do bot.

## 7. Requisitos para replicar em outra máquina

1. n8n rodando em Docker (queue mode ou single) e um Jenkins alcançável por ele.
2. Clonar este repositório e entrar em `n8n/`.
3. `cp .env.example .env` — preencher token do bot (@BotFather), instâncias Jenkins (API token de cada uma) e nome do container n8n.
4. `./deploy.sh` — gera o workflow, importa via CLI do n8n (sem API key), ativa e registra o menu de comandos no Telegram.
5. Adicionar o bot ao grupo, `/chatid`, preencher `ALLOWED_CHAT_IDS`, rodar `./deploy.sh` de novo.

Passo a passo detalhado e tabela de comandos: [n8n/README.md](../n8n/README.md).
