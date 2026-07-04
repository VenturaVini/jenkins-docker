# jenkins-docker

Jenkins em Docker pronto para rodar **robôs Python em containers**, com dois modos de trabalho (projeto vindo do **git** ou rodando **direto do servidor**) e preparado para integração com **n8n**.

Tudo é provisionado automaticamente via **Configuration as Code (JCasC)**: ao subir, o Jenkins já nasce com usuário admin, plugins instalados e dois jobs de exemplo funcionando — sem setup wizard.

## Subir em uma máquina nova (3 passos)

Pré-requisito: Docker + Docker Compose instalados.

```bash
git clone https://github.com/VenturaVini/jenkins-docker.git
cd jenkins-docker
cp .env.example .env   # edite: senha do admin, IP no JENKINS_URL e DOCKER_GID
docker compose up -d --build
```

Antes do `up`, ajuste no `.env`:

- `JENKINS_ADMIN_PASSWORD` — senha do admin;
- `JENKINS_URL` — `http://IP_DA_MAQUINA:3878/`;
- `DOCKER_GID` — resultado de `stat -c %g /var/run/docker.sock`;
- `ROBOS_DIR` — pasta do host com os robôs locais (padrão `../robos`; crie-a se não existir).

Se a máquina **não** tiver n8n, crie a rede esperada pelo compose:

```bash
docker network create n8n_app_network
```

Acesse `http://IP_DA_MAQUINA:3878` e faça login com o usuário/senha do `.env`.

## Como funciona

- O Jenkins roda em container e usa o **Docker do host** através do socket montado (`/var/run/docker.sock`). Cada build sobe um container irmão (ex.: `python:3.12-slim`), roda o robô e o descarta — o Jenkins em si não precisa ter Python.
- A pasta do host definida em `ROBOS_DIR` aparece como `/robos` dentro do Jenkins. Os containers de build a enxergam usando `--volumes-from jenkins`.
- Plugins e configuração ficam versionados aqui ([plugins.txt](plugins.txt) e [casc/jenkins.yaml](casc/jenkins.yaml)); o histórico de builds fica no volume `jenkins_home`.

## Os dois modos de rodar robôs

### Modo local (robô na pasta do servidor)

Coloque o robô em uma subpasta de `robos/` (ex.: `robos/meu-robo/` com `main.py` e `requirements.txt`). O pipeline roda assim:

```groovy
sh 'docker run --rm --volumes-from jenkins -w /robos/meu-robo python:3.12-slim sh -c "pip install -q -r requirements.txt && python main.py"'
```

Exemplo completo: [exemplos/Jenkinsfile-local](exemplos/Jenkinsfile-local) — já implantado como o job **robo-local-exemplo**.

### Modo git (robô em repositório)

O job clona o repositório e roda o script num container Python. Exemplo completo: [exemplos/Jenkinsfile-git](exemplos/Jenkinsfile-git) — já implantado como o job **robo-git-exemplo** (parametrizado: URL do repo, branch e script de entrada).

Para um robô "de verdade", o ideal é colocar um `Jenkinsfile` na raiz do repositório do robô e criar um job *Pipeline from SCM* apontando para ele — assim o pipeline também fica versionado.

**Híbrido git + local**: repositórios git dentro de `robos/` também podem ser clonados pelos jobs usando `REPO_URL=file:///robos/meu-robo` (o clone local está liberado via `ALLOW_LOCAL_CHECKOUT` no compose).

## Integração com n8n

O Jenkins está na rede `n8n_app_network`, então n8n e Jenkins se enxergam pelo nome do container, sem expor portas extras:

- **n8n dispara um job**: nó *HTTP Request* com `POST http://jenkins:8080/generic-webhook-trigger/invoke?token=robo-local-exemplo` (plugin Generic Webhook Trigger; cada job define seu token no bloco `triggers`). Observação: o trigger é registrado na primeira execução do job — rode o job uma vez manualmente antes de usar o webhook.
- **Jenkins avisa o n8n**: no fim do pipeline, `sh 'curl -X POST http://n8n:5678/webhook/meu-fluxo'` (bloco `post { success { ... } }`).
- **🤖 Bot do Telegram**: a pasta [n8n/](n8n/) traz um bot completo (workflow do n8n) para listar, disparar e monitorar os jobs pelo celular — botões inline, aviso quando o build termina, suporte a vários Jenkins. Veja [n8n/README.md](n8n/README.md) e o [PDD do bot](docs/PDD-bot-telegram.md).

## Estrutura

```
docker-compose.yml   # serviço jenkins (porta 3878, socket do Docker, rede do n8n)
Dockerfile           # imagem custom: jenkins LTS + docker CLI + plugins
plugins.txt          # plugins pré-instalados
casc/jenkins.yaml    # configuração automática (admin, segurança, jobs de exemplo)
.env.example         # modelo de configuração por máquina
exemplos/            # Jenkinsfiles de referência (modo local e modo git)
n8n/                 # bot do Telegram (workflow n8n): template, .env.example e deploy.sh
docs/PDD.md          # Documento de Definição de Processo do ambiente
docs/PDD-bot-telegram.md  # PDD do bot Telegram <-> Jenkins
```

## Troubleshooting

- **`permission denied` no docker.sock**: o `DOCKER_GID` do `.env` não bate com o da máquina. Rode `stat -c %g /var/run/docker.sock`, ajuste o `.env` e `docker compose up -d`.
- **Rede `n8n_app_network` não existe**: `docker network create n8n_app_network`.
- **Porta 3878 ocupada**: mude `JENKINS_PORT` no `.env` (e o `JENKINS_URL`).
- **Mudei o casc/jenkins.yaml**: `docker compose restart jenkins` (ou *Manage Jenkins → Configuration as Code → Reload*).
