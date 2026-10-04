# Fase 1 - ambiente usa e getta per riprodurre gli attacchi di red_team_v4 contro la v4.
# La rete serve solo alla costruzione (git, pytest). L'esecuzione avviene con --network none:
# prepara_base() della v4 clona https://github.com/hukkin/tomli.git, e qui una regola
# "insteadOf" nel .gitconfig della home finta reindirizza quel clone a un mirror locale,
# senza modificare pilota_costo_v4.py.
FROM python@sha256:b1b81d67b8df73bf6067191790c233ef9e598b863fc1ccf447956138ca466d99

ARG TOMLI_COMMIT=5a77b12a7a9f052ce5a20c335d2825658f6aea52

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytest==8.3.3

RUN useradd --create-home --home-dir /home/finta --shell /usr/sbin/nologin finto \
 && git clone --quiet --mirror https://github.com/hukkin/tomli.git /opt/tomli.git \
 && git -C /opt/tomli.git cat-file -e "${TOMLI_COMMIT}^{commit}" \
 && chown -R finto:finto /opt/tomli.git

USER finto
RUN git config --global url."/opt/tomli.git".insteadOf https://github.com/hukkin/tomli.git

USER root
COPY pilota_costo_v4.py /opt/rif/pilota_costo_v4.py
COPY red_team_v4/ /opt/rif/red_team_v4/
COPY fase1/esegui_attacco.py /opt/rif/esegui_attacco.py
RUN chmod -R a-w /opt/rif

USER finto
WORKDIR /home/finta
ENTRYPOINT ["python", "/opt/rif/esegui_attacco.py"]
