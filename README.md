# Chiron

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](#-statut-du-projet)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![DuckDB](https://img.shields.io/badge/DuckDB-local-FEF502)](https://duckdb.org/)

Assistant IA pour la préparation des conseils de classe — Génère des synthèses trimestrielles personnalisées à partir des bulletins scolaires (PDF PRONOTE).

## 📊 Statut du projet

**Phase actuelle** : Beta fonctionnelle
- Pipeline complet : PDF → Anonymisation → OCR → Génération LLM → Export
- API FastAPI : tous les endpoints connectés
- UI Streamlit : génération et validation fonctionnelles
- RGPD : anonymisation NER avant envoi cloud

**Prochaines étapes** : Parsing structuré, packaging .exe

Détails complets → [todo.md](todo.md)

## 🔄 Vue d'ensemble

```
PDF PRONOTE → Anonymisation NER → OCR Cloud → Génération LLM → Validation → Export CSV
     │              │                  │              │             │           │
     │         CamemBERT          Mistral OCR    OpenAI/Claude   Humain    Dépseudo
     │         (local)            (cloud)        (cloud)        (local)    (local)
     ▼              ▼                  ▼              ▼             ▼           ▼
  Bulletin    PDF anonymisé      Markdown       Synthèse      Validée    Noms réels
```

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- **Données personnelles jamais envoyées au cloud** (anonymisation PDF avant OCR)
- Style et ton personnalisés via few-shot learning
- Application locale + APIs cloud (OCR, LLM)

## Prérequis

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Clés API : OpenAI et/ou Anthropic, Mistral (OCR)

## Installation

```bash
# Cloner le repo
git clone https://github.com/<votre-username>/chiron.git
cd chiron

# Créer l'environnement virtuel
uv venv

# Activer l'environnement virtuel
# Windows
.venv\Scripts\activate
# Linux/MacOS
source .venv/bin/activate

# Installer les dépendances
uv sync --group dev

# Configurer les clés API
cp .env.example .env
# Éditer .env avec vos clés API

# Exécuter les hooks de pre-commit
pre-commit run --all-files
```

## 🚀 Démarrage rapide

### Lancer l'application

```bash
# Terminal 1 : Backend API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 : Frontend Streamlit
streamlit run app/main.py
```

Ouvrir http://localhost:8501 dans le navigateur.

API Swagger UI disponible sur http://localhost:8000/docs.

### Workflow type

1. **Import** : Uploader les PDF bulletins de la classe
2. **Génération** : Cliquer sur "Générer" (individuel ou batch)
3. **Review** : Relire, éditer si besoin
4. **Validation** : Valider les synthèses finales
5. **Export** : Télécharger le CSV pour le conseil

### Estimation des coûts

| Étape | Coût estimé |
|-------|-------------|
| Mistral OCR | ~$0.02/page |
| Génération LLM (GPT-5-mini) | ~$0.0015/élève |
| **Classe de 30 élèves** | **~$0.65** |

## Configuration (.env)

```env
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# PDF Parser : pdfplumber (gratuit, local) ou mistral_ocr (cloud, payant)
PDF_PARSER_TYPE=pdfplumber
MISTRAL_OCR_API_KEY=...
MISTRAL_OCR_MODEL=mistral-ocr-latest

# Modèle par défaut
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-5-mini

# API Backend
CHIRON_API_HOST=127.0.0.1
API_PORT=8000

# Base de données
DB_PATH=data/db/chiron.duckdb
```

## Structure du projet

```
chiron/
├── src/
│   ├── api/                  # Backend REST FastAPI
│   │   ├── main.py           # App FastAPI + lifespan
│   │   ├── dependencies.py   # Injection de dépendances (get_or_404, repos)
│   │   └── routers/          # classes, eleves, syntheses, exports
│   ├── core/                 # Transverse
│   │   ├── constants.py      # Année scolaire, constantes
│   │   ├── models.py         # Modèles Pydantic (Eleve, Synthese, Alerte...)
│   │   └── exceptions.py     # Hiérarchie d'exceptions custom
│   ├── document/             # Parsing PDF
│   │   ├── pdfplumber_parser.py # Extraction locale (gratuit)
│   │   ├── mistral_parser.py # OCR cloud (Mistral)
│   │   └── anonymizer.py     # Anonymisation NER + PyMuPDF
│   ├── generation/           # Génération synthèses
│   │   ├── generator.py      # SyntheseGenerator (DI)
│   │   ├── prompts.py        # Templates de prompts versionnés (v1, v2)
│   │   └── prompt_builder.py # Formatage données élève pour le prompt
│   ├── llm/                  # Abstraction LLM multi-provider
│   │   ├── manager.py        # LLMManager (registry, retry, rate limiting)
│   │   ├── config.py         # Settings (clés API, modèles, pricing)
│   │   ├── pricing.py        # Calcul de coûts unifié
│   │   └── clients/          # OpenAI, Anthropic, Mistral
│   ├── privacy/              # Pseudonymisation RGPD
│   │   └── pseudonymizer.py  # Mapping nom ↔ ELEVE_XXX (DuckDB séparé)
│   └── storage/              # Persistance DuckDB
│       ├── connection.py     # DuckDBConnection base class
│       ├── schemas.py        # Définitions des tables SQL
│       └── repositories/     # CRUD (classes, eleves, syntheses)
├── app/                      # Frontend Streamlit
│   ├── main.py               # Entry point + navigation
│   ├── api_client.py         # Client HTTP vers l'API FastAPI
│   ├── config.py             # Settings UI (providers, coûts)
│   ├── pages/                # 1_import, 2_syntheses, 3_Export
│   └── components/           # sidebar, eleve_card, synthese_editor...
├── data/
│   └── db/                   # DuckDB (chiron.duckdb, privacy.duckdb)
├── docs/                     # Documentation technique
└── tests/
```

## Sécurité & RGPD

| Aspect | Mesure |
|--------|--------|
| **Anonymisation PDF** | CamemBERT NER + PyMuPDF redaction **avant** envoi cloud |
| **Stockage local** | DuckDB fichier local, pas de cloud |
| **Mapping identités** | Base séparée (`privacy.duckdb`) |
| **OCR cloud** | Reçoit uniquement PDFs **anonymisés** |
| **LLM cloud** | Reçoit uniquement données **pseudonymisées** (ELEVE_XXX) |
| **Validation humaine** | Obligatoire avant export |

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Runtime | Python 3.13+ |
| LLM Chat | OpenAI GPT-5-mini / Claude Sonnet 4.5 |
| LLM OCR | **Mistral OCR** (mistral-ocr-latest) |
| NER | **CamemBERT** (Jean-Baptiste/camembert-ner) |
| PDF manipulation | **PyMuPDF** (fitz) + pdfplumber |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Base de données | DuckDB (local) |
| Validation | Pydantic v2 |
| HTTP async | httpx |
| Retry/backoff | tenacity |

## Documentation

- **[docs/architecture.md](docs/architecture.md)** - Architecture, flux de données, RGPD
- **[todo.md](todo.md)** - Suivi d'avancement

## Notebooks de validation

| Notebook | Description |
|----------|-------------|
| `04_production_simulation.ipynb` | Simulation workflow complet avec anonymisation |
| `05_pdf_anonymization_test.ipynb` | Benchmark NER (spaCy vs CamemBERT) |
| `06_workflow_complet.ipynb` | Workflow end-to-end avec estimation coûts |

## Licence

Projet privé — Usage non commercial.
