FROM jenkins/jenkins:lts-jdk21

USER root

# CLI do Docker + plugin compose (o daemon usado é o do host, via socket montado)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg git \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Repositórios em /robos pertencem ao usuário do host (root), não ao jenkins;
# sem isso o git recusa clones locais com "dubious ownership".
RUN git config --system --add safe.directory '*'

USER jenkins

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
