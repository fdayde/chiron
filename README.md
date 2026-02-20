<p align="center">
  <img src="app/static/chiron_logo.png" alt="Chiron" width="120">
</p>

<h1 align="center">Chiron</h1>

[![CI](https://github.com/fdayde/chiron/actions/workflows/ci.yml/badge.svg)](https://github.com/fdayde/chiron/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/fdayde/chiron/graph/badge.svg)](https://codecov.io/gh/fdayde/chiron)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](#-statut-du-projet)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![DuckDB](https://img.shields.io/badge/DuckDB-local-FEF502)](https://duckdb.org/)

Assistant IA pour la préparation des conseils de classe - Génère des synthèses trimestrielles personnalisées à partir des bulletins scolaires (PDF PRONOTE).

## Fonctionnalités clés

### Pseudonymisation avant envoi cloud
Les noms, prénoms et informations identifiantes sont détectés par un modèle NER local (CamemBERT) et remplacés par des pseudonymes (`ELEVE_001`) **avant tout envoi au cloud**. Le LLM ne reçoit jamais de données nominatives. Les noms réels sont restaurés automatiquement à l'export.

### Few-shot learning — calibration par l'enseignant
L'enseignant peut marquer jusqu'à 3 synthèses validées comme « exemples » pour l'IA. Ces exemples sont automatiquement injectés dans le prompt (few-shot) afin de calibrer le style, le ton et le niveau de détail des synthèses suivantes. Les appréciations sont tronquées et les synthèses plafonnées à 1000 caractères pour maîtriser la taille du prompt.

### Insights pédagogiques fondés sur la recherche
Le prompt de génération est conçu selon des principes issus de la recherche en éducation :
- **Growth mindset** (Dweck, 2006) : valorisation des processus, pas des capacités fixes
- **Feedforward** (Hattie & Timperley, 2007) : orientation prospective vers des stratégies concrètes
- **Théorie de l'autodétermination** (Deci & Ryan, 2000) : profils d'engagement contextuels, pas d'étiquettes figées
- **Détection des biais de genre** : identification automatique des formulations genrées dans les appréciations

## Statut du projet

**Phase actuelle** : Bêta fonctionnelle — packaging `.exe` disponible
- Pipeline complet : PDF → Pseudonymisation → Extraction → Génération LLM → Export
- UI NiceGUI (navigateur) : import, génération, calibration few-shot, validation, export
- API FastAPI intégrée (process unique)
- RGPD : pseudonymisation NER locale avant envoi cloud
- Multi-provider : OpenAI, Anthropic, Mistral
- Distribution : `chiron.exe` (PyInstaller, `--onedir`)

## Vue d'ensemble

```
PDF PRONOTE → Pseudonymisation → Extraction → Calibration → Génération LLM → Validation → Export CSV
     │              │                  │            │               │             │           │
     │         CamemBERT         YAML template  Few-shot       OpenAI/Claude   Humain    Dépseudo
     │         (local)           (local)        (0-3 ex.)      (cloud)        (local)    (local)
     ▼              ▼                  ▼            ▼               ▼             ▼           ▼
  Bulletin    PDF pseudonymisé   Données      Exemples        Synthèse      Validée    Noms réels
```

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- **Noms et prénoms pseudonymisés avant envoi au cloud** (le LLM ne reçoit que des identifiants `ELEVE_XXX`)
- Style et ton calibrés via few-shot learning (exemples de l'enseignant)
- Insights pédagogiques actionnables (alertes, réussites, stratégies, biais de genre)
- Application locale + APIs cloud (LLM)

## Prérequis (mode développeur)

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Clé API : OpenAI et/ou Anthropic et/ou Mistral

## Installation (mode développeur)

```bash
git clone https://github.com/fdayde/chiron.git
cd chiron

uv venv
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

uv sync --group dev

cp .env.example .env
# Éditer .env avec vos clés API
```

## Démarrage rapide

```bash
python run.py
```

Le navigateur s'ouvre sur http://localhost:8080.

Options :
```bash
CHIRON_NATIVE=1 python run.py    # Mode desktop (pywebview)
CHIRON_PORT=9000 python run.py   # Port personnalisé
```

### Workflow type

1. **Classe** : Importer les PDF bulletins de la classe (pseudonymisation automatique)
2. **Génération** : Générer 1-2 synthèses, relire et valider
3. **Calibration** : Marquer 1 à 3 synthèses validées comme exemples pour l'IA
4. **Batch** : Générer les synthèses restantes (calibrées par les exemples)
5. **Review** : Relire, éditer si besoin, valider
6. **Export** : Télécharger les synthèses (noms réels restaurés automatiquement)

## Distribution (.exe)

Pour distribuer l'application sans installer Python :

```bash
# Installer les outils de build
uv pip install pyinstaller pyinstaller-hooks-contrib

# Construire
python scripts/build.py --clean
```

Le dossier `dist/chiron/` contient tout le nécessaire. Pour l'utilisateur final :

1. Renommer `.env.example` en `.env` et remplir sa clé API
2. Double-cliquer sur `chiron.exe`

## Configuration (.env)

```env
# Provider par défaut : openai, anthropic ou mistral
DEFAULT_PROVIDER=anthropic

# Clés API (seule celle du provider choisi est nécessaire)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
```

Options avancées (développeurs) : voir [.env.example](.env.example).

## Structure du projet

```
chiron/
├── src/
│   ├── api/                  # Backend REST FastAPI
│   │   ├── main.py           # App FastAPI + lifespan
│   │   ├── dependencies.py   # Injection de dépendances
│   │   └── routers/          # classes, élèves, synthèses, exports
│   ├── core/                 # Transverse
│   │   ├── constants.py      # Chemins, année scolaire
│   │   ├── models.py         # Modèles Pydantic
│   │   └── exceptions.py     # Exceptions custom
│   ├── document/             # Parsing PDF
│   │   ├── yaml_template_parser.py # Parser principal (template YAML configurable)
│   │   ├── pdfplumber_parser.py    # Parser legacy (rétrocompatibilité)
│   │   ├── anonymizer.py          # Extraction nom élève + NER safety net
│   │   ├── validation.py          # Validation post-extraction + mismatch classe
│   │   ├── debug_visualizer.py    # PDF annoté pour debug visuel
│   │   └── templates/             # Templates YAML d'extraction (pronote_standard)
│   ├── generation/           # Génération synthèses
│   │   ├── generator.py      # SyntheseGenerator
│   │   ├── prompts.py        # Templates de prompts versionnés
│   │   └── prompt_builder.py # Formatage données pour le prompt
│   ├── llm/                  # Abstraction LLM multi-provider
│   │   ├── manager.py        # LLMManager (registry, retry, rate limiting)
│   │   ├── config.py         # Settings (clés API, modèles, pricing)
│   │   ├── base.py           # LLMClient ABC (template method)
│   │   ├── rate_limiter.py   # SimpleRateLimiter (fenêtre glissante RPM)
│   │   ├── pricing.py        # PricingCalculator (calcul de coûts)
│   │   └── clients/          # OpenAI, Anthropic, Mistral
│   ├── privacy/              # Pseudonymisation RGPD
│   │   └── pseudonymizer.py  # Mapping nom <-> ELEVE_XXX
│   └── storage/              # Persistance DuckDB
│       ├── connection.py     # Connexion DuckDB
│       ├── schemas.py        # Définitions des tables SQL
│       └── repositories/     # CRUD (classes, élèves, synthèses)
├── app/                      # Frontend NiceGUI
│   ├── layout.py             # Layout partagé (header, sidebar)
│   ├── config_ng.py          # Settings UI (providers, coûts)
│   ├── cache.py              # Cache TTL
│   ├── state.py              # Gestion d'état
│   ├── pages/                # home, import, synthèses, export, prompt
│   └── components/           # eleve_card, synthese_editor, llm_selector...
├── tests/                    # Tests unitaires (pseudonymisation, purge)
├── run.py                    # Point d'entrée unique (API + UI)
├── chiron.spec               # Spec PyInstaller
├── scripts/build.py          # Script de build .exe
├── data/
│   └── db/                   # DuckDB (chiron.duckdb, privacy.duckdb)
└── docs/                     # Documentation technique
```

## Sécurité & RGPD

| Aspect | Mesure |
|--------|--------|
| **Pseudonymisation** | CamemBERT NER **avant** envoi cloud (ELEVE_XXX) |
| **Stockage local** | DuckDB fichier local, pas de cloud |
| **Mapping identités** | Base séparée (`privacy.duckdb`), cascade suppression |
| **LLM cloud** | Reçoit uniquement données **pseudonymisées** |
| **Validation humaine** | Obligatoire avant export |
| **Purge trimestrielle** | Suppression données + mappings après export (page Export) |
| **Base légale** | Mission de service public éducatif (RGPD Art. 6(1)(e)) |

### Détail des données personnelles

| Donnée | Traitement |
|--------|------------|
| Nom, prénom | Pseudonymisé (ELEVE_XXX) avant envoi à l'IA |
| Genre (F/G) | Extrait du PDF, stocké localement, **non transmis** — le LLM déduit le genre depuis les accords grammaticaux des appréciations |
| Absences, retards | Stocké localement, **non transmis** |
| Moyennes par matière | Catégorisées selon l'échelle de maîtrise du socle commun (LSU) avant envoi à l'IA |
| Appréciations enseignantes | Transmises pseudonymisées à l'IA |
| Engagements (délégué...) | Stocké localement, **non transmis** |
| Nom des professeurs | Stocké localement, **non transmis** |
| Établissement | Stocké localement, **non transmis** |
| Classe (niveau, groupe) | Stocké localement, **non transmis** |
| Année scolaire | Stocké localement, **non transmis** |
| Trimestre | Stocké localement, **non transmis** |

## Adapter à un autre format de bulletin

Le parsing est conçu pour les bulletins **PRONOTE** via un template YAML configurable (`src/document/templates/pronote_standard.yaml`). Pour l'adapter à un autre format, consultez le guide dédié :

**[docs/adapter-format-bulletin.md](docs/adapter-format-bulletin.md)**

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Runtime | Python 3.13+ |
| LLM | OpenAI GPT-5-mini / Claude Sonnet 4.5 / Mistral |
| NER | CamemBERT (Jean-Baptiste/camembert-ner) |
| PDF | pdfplumber + YAML templates (configurable) |
| Backend | FastAPI + Uvicorn |
| Frontend | NiceGUI |
| Base de données | DuckDB (local) |
| Packaging | PyInstaller (`--onedir`) |

## Documentation

- **[docs/architecture.md](docs/architecture.md)** — Architecture, flux de données, RGPD
- **[docs/adapter-format-bulletin.md](docs/adapter-format-bulletin.md)** — Guide d'adaptation à un autre format de bulletin
- **[docs/plan-rgpd-remediation.md](docs/plan-rgpd-remediation.md)** — Plan de remédiation RGPD (audit et corrections)

## Licence

Ce logiciel est propriétaire. Voir [LICENSE](LICENSE) pour les détails.
Distribution et modification interdites sans autorisation écrite de l'auteur.
