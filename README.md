<p align="center">
  <img src="app/static/chiron_logo.png" alt="Chiron" width="120">
</p>

<h1 align="center">Chiron</h1>

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](#-statut-du-projet)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![DuckDB](https://img.shields.io/badge/DuckDB-local-FEF502)](https://duckdb.org/)

Assistant IA pour la preparation des conseils de classe — Genere des syntheses trimestrielles personnalisees a partir des bulletins scolaires (PDF PRONOTE).

## Statut du projet

**Phase actuelle** : Beta fonctionnelle — packaging `.exe` disponible
- Pipeline complet : PDF → Anonymisation → Extraction → Generation LLM → Export
- UI NiceGUI (navigateur) : import, generation, validation, export
- API FastAPI integree (process unique)
- RGPD : anonymisation NER locale avant envoi cloud
- Distribution : `chiron.exe` (PyInstaller, `--onedir`)

## Vue d'ensemble

```
PDF PRONOTE → Anonymisation NER → Extraction → Generation LLM → Validation → Export CSV
     │              │                  │              │             │           │
     │         CamemBERT          pdfplumber     OpenAI/Claude   Humain    Depseudo
     │         (local)            (local)        (cloud)        (local)    (local)
     ▼              ▼                  ▼              ▼             ▼           ▼
  Bulletin    PDF anonymise      Donnees        Synthese      Validee    Noms reels
```

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- **Donnees personnelles jamais envoyees au cloud** (anonymisation PDF avant extraction)
- Style et ton personnalises via few-shot learning
- Application locale + APIs cloud (LLM)

## Prerequis (mode developpeur)

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Cle API : OpenAI et/ou Anthropic et/ou Mistral

## Installation (mode developpeur)

```bash
git clone https://github.com/<votre-username>/chiron.git
cd chiron

uv venv
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

uv sync --group dev

cp .env.example .env
# Editer .env avec vos cles API
```

## Demarrage rapide

```bash
python run.py
```

Le navigateur s'ouvre sur http://localhost:8080.

Options :
```bash
CHIRON_NATIVE=1 python run.py    # Mode desktop (pywebview)
CHIRON_PORT=9000 python run.py   # Port personnalise
```

### Workflow type

1. **Import** : Uploader les PDF bulletins de la classe
2. **Generation** : Cliquer sur "Generer" (individuel ou batch)
3. **Review** : Relire, editer si besoin
4. **Validation** : Valider les syntheses finales
5. **Export** : Telecharger le CSV pour le conseil

## Distribution (.exe)

Pour distribuer l'application sans installer Python :

```bash
# Installer les outils de build
uv pip install pyinstaller pyinstaller-hooks-contrib

# Construire
python scripts/build.py --clean
```

Le dossier `dist/chiron/` contient tout le necessaire. Pour l'utilisateur final :

1. Renommer `.env.example` en `.env` et remplir sa cle API
2. Double-cliquer sur `chiron.exe`

## Configuration (.env)

```env
# Provider par defaut : openai, anthropic ou mistral
DEFAULT_PROVIDER=anthropic

# Cles API (seule celle du provider choisi est necessaire)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
```

Options avancees (developpeurs) : voir [.env.example](.env.example).

## Structure du projet

```
chiron/
├── src/
│   ├── api/                  # Backend REST FastAPI
│   │   ├── main.py           # App FastAPI + lifespan
│   │   ├── dependencies.py   # Injection de dependances
│   │   └── routers/          # classes, eleves, syntheses, exports
│   ├── core/                 # Transverse
│   │   ├── constants.py      # Chemins, annee scolaire
│   │   ├── models.py         # Modeles Pydantic
│   │   └── exceptions.py     # Exceptions custom
│   ├── document/             # Parsing PDF
│   │   ├── pdfplumber_parser.py  # Extraction locale
│   │   ├── mistral_parser.py     # OCR cloud (Mistral)
│   │   └── anonymizer.py        # Anonymisation NER + PyMuPDF
│   ├── generation/           # Generation syntheses
│   │   ├── generator.py      # SyntheseGenerator
│   │   ├── prompts.py        # Templates de prompts versiones
│   │   └── prompt_builder.py # Formatage donnees pour le prompt
│   ├── llm/                  # Abstraction LLM multi-provider
│   │   ├── manager.py        # LLMManager (registry, retry, rate limiting)
│   │   ├── config.py         # Settings (cles API, modeles, pricing)
│   │   └── clients/          # OpenAI, Anthropic, Mistral
│   ├── privacy/              # Pseudonymisation RGPD
│   │   └── pseudonymizer.py  # Mapping nom <-> ELEVE_XXX
│   └── storage/              # Persistance DuckDB
│       ├── connection.py     # Connexion DuckDB
│       ├── schemas.py        # Definitions des tables SQL
│       └── repositories/     # CRUD (classes, eleves, syntheses)
├── app/                      # Frontend NiceGUI
│   ├── layout.py             # Layout partage (header, sidebar)
│   ├── config_ng.py          # Settings UI (providers, couts)
│   ├── cache.py              # Cache TTL
│   ├── state.py              # Gestion d'etat
│   ├── pages/                # home, import, syntheses, export, prompt
│   └── components/           # eleve_card, synthese_editor, llm_selector...
├── run.py                    # Point d'entree unique (API + UI)
├── chiron.spec               # Spec PyInstaller
├── scripts/build.py          # Script de build .exe
├── data/
│   └── db/                   # DuckDB (chiron.duckdb, privacy.duckdb)
└── docs/                     # Documentation technique
```

## Securite & RGPD

| Aspect | Mesure |
|--------|--------|
| **Anonymisation PDF** | CamemBERT NER + PyMuPDF redaction **avant** envoi cloud |
| **Stockage local** | DuckDB fichier local, pas de cloud |
| **Mapping identites** | Base separee (`privacy.duckdb`) |
| **LLM cloud** | Recoit uniquement donnees **pseudonymisees** (ELEVE_XXX) |
| **Validation humaine** | Obligatoire avant export |

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Runtime | Python 3.13+ |
| LLM | OpenAI GPT-5-mini / Claude Sonnet 4.5 / Mistral |
| NER | CamemBERT (Jean-Baptiste/camembert-ner) |
| PDF | PyMuPDF + pdfplumber |
| Backend | FastAPI + Uvicorn |
| Frontend | NiceGUI |
| Base de donnees | DuckDB (local) |
| Packaging | PyInstaller (`--onedir`) |

## Documentation

- **[docs/architecture.md](docs/architecture.md)** — Architecture, flux de donnees, RGPD

## Licence

Projet prive — Usage non commercial.
