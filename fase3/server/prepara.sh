#!/usr/bin/env bash
# Preparazione del server di prova (Hetzner CX23, Debian 12 "bookworm").
# DA RILEGGERE PRIMA DI LANCIARLO. Non esegue nulla della v5: prepara solo l'ambiente.
# Esegue come root (o con sudo). Idempotente: si può rilanciare.
#
# Fa: Docker Engine dal repository ufficiale con versione FISSATA; utente non root nel gruppo
# docker; firewall con solo SSH in ingresso; Python e git; verifica che non ci sia una chiave API.
# NON installa la chiave API: la v5 nelle fasi 0-4 non la usa (CLAUDE.md, regola 1).
set -euo pipefail

# --- versione fissata (parità col PC: config DOCKER_ENGINE = 29.8.1) -------------------------
VERSIONE_DOCKER="5:29.8.1-1~debian.12~bookworm"
UTENTE="${1:-morgan}"            # utente non root da creare/usare; primo argomento, predefinito "morgan"

if [ "$(id -u)" -ne 0 ]; then echo "esegui come root (o con sudo)"; exit 1; fi

# --- 0. nessuna chiave API nell'ambiente (regola 1) ------------------------------------------
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then echo "ANTHROPIC_API_KEY impostata: fermati e avvisa Morgan"; exit 1; fi
grep -rqs ANTHROPIC_API_KEY /etc/environment /root/.bashrc /root/.profile && { echo "chiave nei profili: stop"; exit 1; } || true

# --- 1. pacchetti di base --------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg git python3 python3-venv ufw

# --- 2. repository ufficiale di Docker --------------------------------------------------------
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list
apt-get update

# --- 3. Docker Engine con versione FISSATA e bloccata -----------------------------------------
apt-get install -y \
  docker-ce="${VERSIONE_DOCKER}" docker-ce-cli="${VERSIONE_DOCKER}" \
  containerd.io docker-buildx-plugin
apt-mark hold docker-ce docker-ce-cli          # non si aggiorna da solo (regola 8 / lezione della fase 2)
systemctl enable --now docker

# --- 4. utente non root nel gruppo docker -----------------------------------------------------
if ! id "$UTENTE" >/dev/null 2>&1; then adduser --disabled-password --gecos "" "$UTENTE"; fi
usermod -aG docker "$UTENTE"

# --- 5. firewall: solo SSH in ingresso --------------------------------------------------------
ufw --force reset
ufw default deny incoming
ufw default allow outgoing          # l'uscita serve solo per il git clone di tomli in prepara_tomli
ufw allow OpenSSH
ufw --force enable

# --- 6. riepilogo (nessuna misura) ------------------------------------------------------------
echo "---- preparato ----"
docker --version
docker info --format 'driver cgroup: {{.CgroupDriver}} | cgroup v{{.CgroupVersion}} | kernel {{.KernelVersion}}'
echo "utente docker: $UTENTE"; ufw status | head
echo "Prossimo (come $UTENTE, non root): clonare il repository privato, creare un venv, poi"
echo "  V5_AMBIENTE=server_hetzner python3 v5/supervisore.py oracolo --due-volte   (prova di portabilità)"
echo "I valori DA_LEGGERE del profilo server_hetzner (engine, api, kernel, driver cgroup, ambiente"
echo "ammesso) si fissano con la fase 0 (controlli) e si registrano in config.py."
