## ragow (mittenwalde-spielt.de) – Maintainer-Doku

Dieses Repository enthält die Quellen für die statische Website `mittenwalde-spielt.de` (Hugo) inklusive Kalender-Spiegelung (ICS) und automatischer Generierung der Ausfalltermine.

### Technologien

- **Hugo** (Static Site Generator)
- **Theme**: `hugo-scroll` (als **Git-Submodule**)
- **GitHub Pages** (Hosting)
- **GitHub Actions** (Build/Deploy + Kalender-Sync)
- **Python** (Generator für Ausfalltermine aus der ICS)
- **Renovate** (automatische Updates von Action-/Tool-Versionen)

### Projektstruktur (wichtige Pfade)

#### Hugo Content

- `hugo.toml`: Hugo-Konfiguration (Base URL, Theme, Sprachen)
- `content/de/_index.md`: Startseiten-Header (Hero-Bild, Logo, Headlines)
- `content/de/homepage/index.md`: **Headless Bundle** für die One-Page-Sektionen
- `content/de/homepage/*.md`: Sektionen der Homepage (z. B. `opener.md`, `data.md`, `skip.md`, `contact.md`, `announcement.md`)

#### Hugo Templates (Overrides)

- `layouts/partials/announcement.html`: rendert das Banner aus `content/de/homepage/announcement.md`
- `layouts/partials/custom_head.html`: zusätzliche Styles/Head-Anpassungen
- `layouts/shortcodes/webcal.html`: Shortcode, um `webcal://…` als Link auszugeben (ohne Hugo/Go-Template “Sanitizing”)

#### Kalender & Generator

- `static/Mittenwalde-spielt.ics`: lokal gespiegelte Kalenderdatei (öffentlich unter `/Mittenwalde-spielt.ics`)
- `scripts/generate_cancelled_dates.py`: extrahiert Ausfalltermine aus der ICS und schreibt sie in `skip.md`
- `scripts/requirements.txt`: Python Dependencies (gepinned)
- `data/skip_labels.yml`: Mapping `YYYY-MM-DD → Label` (z. B. Feiertag), wird in der generierten Liste als `(Label)` angehängt

#### CI / Automation

- `.github/workflows/hugo.yml`: Build + Deploy nach GitHub Pages (on push auf `main`)
- `.github/workflows/sync-calendar.yml`: Cron-Job (alle 2h): ICS holen → Ausfalltermine generieren → commit/push
- `renovate.json`: Renovate-Konfiguration (inkl. Regex-Update für `hugo-version` in Workflows)

---

## Deploy-Flow (Website)

### GitHub Action: Deploy Hugo to GitHub Pages

Workflow: `.github/workflows/hugo.yml`

- **Trigger**: `push` auf `main` oder manuell (`workflow_dispatch`)
- **Schritte**:
  - Checkout inkl. Submodule
  - Setup Hugo (Version gepinnt in `hugo.yml`)
  - `hugo --minify`
  - Upload `./public` als Pages Artifact
  - Deploy nach GitHub Pages

---

## Kalender-Flow (Radicale → Website)

### Ziel

- Nutzer sollen den Kalender über die Website abonnieren oder herunterladen, ohne den Radicale-Link zu sehen.
- Die Website spiegelt deshalb eine lokale ICS unter `/Mittenwalde-spielt.ics`.
- Ausfälle (“Ausfalltermine”) werden aus der ICS extrahiert und in `content/de/homepage/skip.md` zwischen Markern aktualisiert.

### GitHub Action: Sync calendar ICS

Workflow: `.github/workflows/sync-calendar.yml`

- **Trigger**:
  - Zeitplan: alle 2 Stunden (`cron: "0 */2 * * *"`)
  - manuell (`workflow_dispatch`)
- **Schritte**:
  1) Checkout (mit PAT), damit ein Push anschließend den Deploy-Workflow triggern kann
  2) Download der ICS via `curl` (Basic Auth) + Validierung (`BEGIN:VCALENDAR`)
  3) Speichern als `static/Mittenwalde-spielt.ics`
  4) Python Setup + Installation der Dependencies
  5) Generator: `python scripts/generate_cancelled_dates.py`
  6) Commit + Push, wenn sich `static/Mittenwalde-spielt.ics` oder `content/de/homepage/skip.md` geändert hat
  7) Push triggert `hugo.yml` → neuer Deploy

### Ausfalltermine-Generierung (Details)

Script: `scripts/generate_cancelled_dates.py`

- **Input**: `static/Mittenwalde-spielt.ics`
- **Zusätzliche Labels**: `data/skip_labels.yml` (`YYYY-MM-DD: Text`)
- **Erkennung von Ausfällen**:
  - `EXDATE` (Ausnahmen bei wiederkehrenden Events)
  - `VEVENT` mit `STATUS:CANCELLED` (z. B. Einzelabsage; ggf. `RECURRENCE-ID`)
- **Filter**: nur **heute oder Zukunft** in Zeitzone `Europe/Berlin`
- **Output**: ersetzt nur den generierten Block in `content/de/homepage/skip.md`:

```md
<!-- BEGIN GENERATED: cancelled-dates -->
... generated list ...
<!-- END GENERATED: cancelled-dates -->
```

### Kalender-Link auf der Website

Seite: `content/de/homepage/skip.md`

- Abonnieren: über Shortcode (damit `webcal://` funktioniert)
- Download: Link auf `/Mittenwalde-spielt.ics`

---

## Secrets / Credentials (GitHub)

Für `.github/workflows/sync-calendar.yml` werden folgende Secrets benötigt:

- `RADICALE_URL`: URL, die eine ICS ausliefert (ohne Credentials in der URL)
- `RADICALE_USERNAME`: Username für Basic Auth
- `RADICALE_PASSWORD`: Password für Basic Auth
- `CALENDAR_SYNC_PAT`: PAT (fine-grained ist ok) mit mindestens:
  - Zugriff auf dieses Repo
  - Permission: **Contents: Read and write**

Warum PAT? Standard-Pushes aus Workflows mit `GITHUB_TOKEN` triggern üblicherweise keine weiteren Workflows (`on: push`). Mit PAT werden Deploys wieder zuverlässig angestoßen.

---

## Renovate (Dependencies automatisch aktualisieren)

Konfiguration: `renovate.json`

- Updatet GitHub Actions (`uses: …@v4`, Manager `github-actions`)
- Updatet Python requirements (Manager `pip_requirements`)
- Updatet den Hugo-Pin in `.github/workflows/hugo.yml` via `regexManagers` (Datasource: GitHub Releases `gohugoio/hugo`)
- Auto-Merge ist aktiviert (Repo muss “Allow auto-merge” erlauben; Branch Protection muss kompatibel sein)

Hinweis: Hugo-Updates können regressionsanfällig sein. Falls Builds nach einem Hugo-Bump brechen, den Pin in `.github/workflows/hugo.yml` wieder auf eine funktionierende Version zurücksetzen.

---

## Lokale Entwicklung / Testen

### Voraussetzungen

- `git` (inkl. Submodule)
- **Hugo Extended** (am besten die Version, die CI nutzt; siehe `.github/workflows/hugo.yml`)
- **Python** (für Generator-Script)
- `pip`

### Setup

Submodule initialisieren:

```bash
git submodule update --init --recursive
```

Lokalen Server starten:

```bash
hugo server
```

Drafts anzeigen (z. B. `content/de/homepage/announcement.md` hat häufig `draft: true`):

```bash
hugo server -D
```

### Generator lokal ausführen

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/generate_cancelled_dates.py
```

Erwartung: `content/de/homepage/skip.md` wird zwischen den Markern aktualisiert.

---

## Troubleshooting (kurz)

### Kalender wird nicht aktualisiert

- `Sync calendar ICS` Workflow-Run prüfen (Download-Step + `BEGIN:VCALENDAR`-Check)
- Prüfen, ob `RADICALE_URL` wirklich ICS liefert (keine HTML/Login-Seite)

### Deploy läuft nicht nach Sync

- Prüfen, ob Checkout im Sync-Workflow den PAT nutzt (`token: ${{ secrets.CALENDAR_SYNC_PAT }}`)
- Ohne PAT kann ein Workflow-Push den Deploy-Workflow blockieren

### `webcal://` wird zu `#ZgotmplZ`

- `webcal://` niemals als “normalen” Markdown-Link ausgeben
- Stattdessen `layouts/shortcodes/webcal.html` + Shortcode-Usage in `skip.md` nutzen
