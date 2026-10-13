# Security policy

In this project a "vulnerability" is mainly a way for the **candidate** — the submitted `_parser.py` — to influence the judge's verdict other than by being genuinely correct and faster. Reports of that kind are the most valuable contribution this repository can receive.

## In scope

- Any way for a candidate to make **v5** report a wrong outcome: reading the oracle, tests or final; altering the timing or the memory measurement; recognising cases; keeping state across episodes; escaping the container boundary; producing output the host misreads.
- Any way to reconstruct cases of the **secret final** from published material.
- Credentials, secrets or private data found anywhere in the repository or its history.

## Out of scope

- Weaknesses of **v4**. v4 is kept deliberately vulnerable as a reference; its known attacks are documented in the attack register.
- Gains that come from the worker living in the candidate's process (PATCH_WORKER): this limit is known and measured (up to 1.1124× on DEV, 1.1755× on the fixture final), and the B threshold accounts for it.
- The limits already listed in the README and in `docs/REPORT.md`.

## How to report

Please **do not open a public issue** for a new attack or a leak. Use GitHub's private vulnerability reporting: the **Security** tab of this repository → **Report a vulnerability**.

A useful report includes:

1. the SHA-256 of the candidate file and the commit of the judge you used;
2. the reference on which the attack succeeds (v4, or v5 with *one* named defence removed) and the outcome on the real v5 — the project's parent rule: a defence counts only if the attack succeeds on a vulnerable reference and then fails on v5;
3. the commands you ran and your environment (OS, Docker version, Python version);
4. the observed verdicts, as JSON where possible.

Never include API keys or other credentials in a report. Run candidates only inside your own disposable containers, with no network and no credentials in the environment.

## What happens next

This is a one-maintainer project, handled on a best-effort basis. A confirmed new attack is added to the attack register with its outcome and credited to the reporter unless they prefer otherwise. Public disclosure happens after the attack is documented, or after 90 days, whichever comes first, unless agreed otherwise.

The concluded pilot and its STOP decision are frozen: a new attack is reported as a new finding, it does not rewrite past results.
