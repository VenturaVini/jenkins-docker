# PDD — Documento de Definição de Processo

**Processo:** Orquestração de robôs Python em containers via Jenkins
**Versão:** 1.0 — 02/07/2026
**Responsável:** Vinícius Ventura (vini.ventura98@gmail.com)

---

## 1. Objetivo

Padronizar a execução de robôs (automações em Python) em um servidor Linux usando Jenkins como orquestrador. Cada robô roda isolado em um container Docker descartável, com logs, histórico e agendamento centralizados no Jenkins. O ambiente inteiro é reproduzível: basta clonar o repositório e subir com Docker Compose em qualquer máquina.

## 2. Escopo

| Item | Descrição |
|---|---|
| Ferramenta de orquestração | Jenkins LTS (container Docker) |
| Execução dos robôs | Containers `python:3.12-slim` descartáveis (um por build) |
| Origem dos projetos | Modo **git** (clona repositório) e modo **local** (pasta `robos/` do servidor) |
| Disparo | Manual, agendado (cron do Jenkins) ou webhook (n8n) |
| Fora de escopo | HTTPS/proxy reverso, robôs não-Python (possível, mas não coberto pelos exemplos) |

## 3. Arquitetura

```
┌──────────────────────── Servidor (Docker host) ────────────────────────┐
│                                                                        │
│  ┌─────────────┐  socket   ┌──────────────────────────────┐            │
│  │   Jenkins   ├──────────▶│ docker run python:3.12-slim  │ (efêmero)  │
│  │  :3878→8080 │           │  └─ roda o robô e é removido │            │
│  └──────┬──────┘           └──────────────────────────────┘            │
│         │ rede n8n_app_network                                         │
│  ┌──────▼──────┐   ┌──────────┐   ┌───────┐                            │
│  │     n8n     │   │ postgres │   │ redis │   (já existentes)          │
│  └─────────────┘   └──────────┘   └───────┘                            │
│                                                                        │
│  /root/projetos/robos ──montada como /robos no Jenkins                 │
└────────────────────────────────────────────────────────────────────────┘
```

Decisões técnicas:

- **Docker socket mount (DooD)** em vez de Docker-in-Docker: o Jenkins usa o daemon do host; containers de build são "irmãos" do Jenkins. Sem modo privileged.
- **Configuration as Code (JCasC)**: admin, segurança, plugins e jobs de exemplo nascem prontos no primeiro boot. Nada de setup wizard.
- **`--volumes-from jenkins`** nos containers de build: dá acesso ao workspace (volume `jenkins_home`) e à pasta `/robos` sem depender de caminhos do host.
- **Portas fora da faixa comum**: web em **3878** e agentes JNLP em **3879** (configuráveis no `.env`). Escolhidas de propósito fora das portas clássicas (8080/8081/50000) porque o servidor já roda vários serviços Docker nelas (evolution_api na 8080, por exemplo).

## 4. Fluxos do processo

### 4.1 Robô em modo local

1. Desenvolvedor coloca o robô em `robos/<nome-do-robo>/` (com `main.py` e `requirements.txt`).
2. Cria um job Pipeline no Jenkins (pode copiar o `robo-local-exemplo`).
3. No build, o Jenkins executa `docker run --rm --volumes-from jenkins -w /robos/<nome-do-robo> python:3.12-slim ...`, que instala as dependências e roda o robô.
4. Log completo fica no build; o container é descartado.

### 4.2 Robô em modo git

1. Robô vive em um repositório git (idealmente com `Jenkinsfile` na raiz).
2. Job no Jenkins clona o repositório (`git url/branch`) para o workspace.
3. Mesmo padrão de execução em container Python descartável, com `-w "$WORKSPACE"`.
4. Job `robo-git-exemplo` demonstra o fluxo com parâmetros (URL, branch, entrypoint).

### 4.3 Disparo via n8n (integração futura)

1. Job Jenkins declara `GenericTrigger(token: '<token-do-job>')` (registrado após a 1ª execução manual).
2. Fluxo n8n usa nó HTTP Request: `POST http://jenkins:8080/generic-webhook-trigger/invoke?token=<token-do-job>` (comunicação interna pela rede `n8n_app_network`).
3. Opcionalmente o pipeline notifica o n8n ao terminar: `curl -X POST http://n8n:5678/webhook/<fluxo>` no bloco `post`.

### 4.4 Operação via Telegram

Implementada em 03/07/2026: bot do Telegram (workflow no n8n) para listar, disparar e monitorar os jobs pelo celular. Processo próprio em [PDD-bot-telegram.md](PDD-bot-telegram.md); instalação em [n8n/README.md](../n8n/README.md).

## 5. Ambiente e acesso

| Campo | Valor |
|---|---|
| name | Jenkins Robôs (produção) |
| url | http://209.50.241.178:3878/ |
| username | definido em `.env` (`JENKINS_ADMIN_USER`) |
| password | definido em `.env` (`JENKINS_ADMIN_PASSWORD`) |

> As credenciais reais **não** são versionadas — vivem apenas no arquivo `.env` do servidor (gitignorado). Em máquina nova, copie `.env.example` para `.env` e defina novos valores.

## 6. Operação e manutenção

| Tarefa | Comando |
|---|---|
| Subir/atualizar | `docker compose up -d --build` |
| Ver logs do Jenkins | `docker logs -f jenkins` |
| Reiniciar | `docker compose restart jenkins` |
| Backup do histórico | volume `jenkins_home` (ex.: `docker run --rm -v jenkins-docker_jenkins_home:/data -v $PWD:/bkp alpine tar czf /bkp/jenkins_home.tgz /data`) |
| Adicionar plugin | incluir em `plugins.txt` e rebuildar |
| Mudar configuração | editar `casc/jenkins.yaml` e reiniciar |

## 7. Requisitos para replicar em outra máquina

1. Docker + Docker Compose instalados.
2. `git clone https://github.com/VenturaVini/jenkins-docker.git && cd jenkins-docker`
3. `cp .env.example .env` e preencher senha, IP e `DOCKER_GID` (`stat -c %g /var/run/docker.sock`).
4. `docker network create n8n_app_network` (se a máquina não tiver n8n).
5. Criar a pasta de robôs (padrão: `../robos`).
6. `docker compose up -d --build`.
