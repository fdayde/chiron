# Chiron

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
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

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Clés API : OpenAI et/ou Anthropic, Mistral (OCR)

## Installation

```bash
# Cloner le repo
git clone https://github.com/[user]/chiron.git
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
| Génération LLM (GPT-4o-mini) | ~$0.002/élève |
| **Classe de 30 élèves** | **~$0.70** |

## Configuration (.env)

```env
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Mistral OCR (peut être la même que MISTRAL_API_KEY)
MISTRAL_OCR_API_KEY=...

# Modèle par défaut
DEFAULT_LLM_PROVIDER=openai
USE_TEST_MODELS=false  # true pour utiliser les modèles économiques
```

## Structure du projet

```
chiron/
├── src/
│   ├── llm/                  # Abstraction LLM multi-provider
│   │   ├── manager.py        # LLMManager (registry pattern, rate limiting)
│   │   ├── config.py         # Settings (clés API, modèles, pricing)
│   │   └── clients/          # OpenAI, Anthropic, Mistral
│   ├── document/             # Parsing PDF
│   │   ├── mistral_parser.py # OCR cloud (Mistral)
│   │   ├── pdfplumber_parser.py # Extraction locale
│   │   └── anonymizer.py     # Anonymisation NER + PyMuPDF
│   ├── privacy/              # Pseudonymisation RGPD
│   │   └── pseudonymizer.py  # Mapping nom ↔ ELEVE_XXX
│   ├── storage/              # Persistance DuckDB
│   │   ├── connection.py     # DuckDBConnection base class
│   │   └── repositories/     # CRUD (héritent de DuckDBConnection)
│   ├── generation/           # Génération synthèses
│   │   ├── generator.py      # SyntheseGenerator (DI)
│   │   └── prompt_builder.py # Construction prompts few-shot
│   ├── api/                  # Backend REST FastAPI
│   │   └── routers/          # classes, eleves, syntheses, exports
│   └── core/                 # Config, models, utils
├── app/                      # Frontend Streamlit
│   ├── main.py
│   ├── pages/                # Import, Review, Export
│   └── components/           # UI components
├── data/
│   ├── raw/                  # PDFs importés
│   ├── processed/            # PDFs anonymisés
│   ├── db/                   # DuckDB (chiron.duckdb, privacy.duckdb)
│   └── exports/              # CSV exportés
├── notebooks/                # Développement et tests
│   ├── 04_production_simulation.ipynb
│   ├── 05_pdf_anonymization_test.ipynb
│   └── 06_workflow_complet.ipynb
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
| Runtime | Python 3.11+ |
| LLM Chat | OpenAI GPT-4o-mini / Claude Sonnet |
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

- **[docs/01_architecture_technique.md](docs/01_architecture_technique.md)** - Architecture détaillée + workflow
- **[docs/02_plan_implementation.md](docs/02_plan_implementation.md)** - Plan d'implémentation par phases
- **[docs/03_README_chiron.md](docs/03_README_chiron.md)** - Documentation projet
- **[todo.md](todo.md)** - Suivi d'avancement et décisions

## Notebooks de validation

| Notebook | Description |
|----------|-------------|
| `04_production_simulation.ipynb` | Simulation workflow complet avec anonymisation |
| `05_pdf_anonymization_test.ipynb` | Benchmark NER (spaCy vs CamemBERT) |
| `06_workflow_complet.ipynb` | Workflow end-to-end avec estimation coûts |

## Licence

Projet privé — Usage non commercial.
