# Chiron

> Assistant IA pour la préparation des conseils de classe

> Dernière mise à jour : 2026-01-26

---

## Description

Chiron est un outil destiné aux professeurs principaux pour générer des synthèses trimestrielles personnalisées à partir des bulletins scolaires (PDF PRONOTE).

**Workflow** :
1. Import des PDF bulletins
2. Anonymisation automatique (NER + PyMuPDF) avant envoi cloud
3. Extraction OCR (Mistral OCR)
4. Pseudonymisation des données
5. Génération de synthèses par LLM (style adapté via few-shot)
6. Validation/édition par le professeur
7. Export CSV (dépseudonymisé) pour le conseil de classe

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- **Données personnelles jamais envoyées au cloud** (anonymisation PDF avant OCR)
- Style et ton personnalisés via exemples du professeur (few-shot)
- Application locale + APIs cloud (OCR, LLM)

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Runtime | Python 3.11+ |
| LLM Chat | OpenAI GPT-4o-mini / Claude Sonnet |
| LLM OCR | **Mistral OCR** (mistral-ocr-latest) |
| NER | **CamemBERT** (Jean-Baptiste/camembert-ner) |
| PDF manipulation | **PyMuPDF** (fitz) + pdfplumber |
| Backend | FastAPI |
| Frontend | Streamlit |
| Base de données | DuckDB (local) |
| Validation | Pydantic v2 |

---

## Installation

```bash
# Cloner le repo
git clone https://github.com/[user]/chiron.git
cd chiron

# Créer environnement virtuel (avec uv)
uv venv
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows

# Installer dépendances
uv pip install -e .

# Configurer
cp .env.example .env
# Éditer .env avec vos clés API
```

---

## Configuration (.env)

```env
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Mistral OCR
MISTRAL_OCR_API_KEY=...
MISTRAL_OCR_MODEL=mistral-ocr-latest

# Default LLM
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini

# API
API_HOST=0.0.0.0
API_PORT=8000

# Database
DB_PATH=data/db/chiron.duckdb
```

---

## Usage

### Démarrer l'application

```bash
# Terminal 1 : Backend API
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 : Frontend Streamlit
streamlit run app/main.py
```

Ouvrir http://localhost:8501 dans le navigateur.

### Workflow type

1. **Import** : Uploader un PDF bulletin de classe
2. **Exemples** : Ajouter 2-3 synthèses rédigées manuellement (few-shot)
3. **Génération** : Cliquer sur "Générer" pour chaque élève
4. **Review** : Relire, éditer si besoin
5. **Validation** : Valider les synthèses finales
6. **Export** : Télécharger le CSV pour le conseil

---

## Structure du projet

```
chiron/
├── src/
│   ├── llm/              # Abstraction LLM multi-provider
│   │   ├── manager.py    # LLMManager avec registry pattern
│   │   ├── config.py     # Settings + get_pricing()
│   │   └── clients/      # OpenAI, Anthropic, Mistral
│   ├── document/         # Parsing PDF (pdfplumber + Mistral OCR)
│   │   └── anonymizer.py # Anonymisation NER + PyMuPDF
│   ├── privacy/          # Pseudonymisation RGPD
│   ├── storage/          # DuckDB + repositories
│   │   ├── connection.py # DuckDBConnection base class
│   │   └── repositories/ # Héritent de DuckDBConnection
│   ├── generation/       # Prompts et génération synthèses (DI)
│   ├── api/              # FastAPI routers
│   └── core/             # Config, models, utils
├── app/                  # Streamlit frontend
│   ├── main.py
│   ├── pages/            # Import, Review, Export
│   └── components/       # UI components
├── data/
│   ├── raw/              # PDFs importés
│   ├── processed/        # PDFs anonymisés
│   ├── db/               # DuckDB
│   └── exports/          # CSV
├── notebooks/            # Dev notebooks
│   ├── 01_parser_dev.ipynb
│   ├── 02_generation_test.ipynb
│   ├── 03_parser_benchmark.ipynb
│   ├── 04_production_simulation.ipynb
│   ├── 05_pdf_anonymization_test.ipynb
│   └── 06_workflow_complet.ipynb
├── tests/
├── docs/
└── scripts/
```

---

## Schémas de données

### Extraction (input)

```python
class EleveExtraction(BaseModel):
    eleve_id: str | None        # Après pseudonymisation
    nom: str | None             # Avant pseudonymisation
    prenom: str | None
    genre: Literal["Fille", "Garçon"] | None
    classe: str | None
    trimestre: int | None
    matieres: list[MatiereExtraction]
    moyenne_generale: float | None
    engagements: list[str]
    absences_demi_journees: int | None
    raw_text: str | None        # Markdown OCR brut
```

### Génération (output LLM)

```python
class SyntheseGeneree(BaseModel):
    synthese_texte: str
    alertes: list[Alerte]           # Notes < 8, problèmes
    reussites: list[Reussite]       # Points forts
    posture_generale: Literal["actif", "passif", "perturbateur", "variable"]
    axes_travail: list[str]         # Priorités d'amélioration
```

---

## Documentation technique

Voir les documents de référence :
- `docs/01_architecture_technique.md` — Architecture détaillée
- `docs/02_plan_implementation.md` — Plan d'implémentation par phases
- `TODO.md` — Suivi d'avancement

---

## Status actuel

| Module | Status |
|--------|--------|
| Parser PDF (Mistral OCR) | ✅ Fonctionnel |
| Anonymisation NER | ✅ Intégré dans MistralOCRParser |
| Pseudonymisation | ✅ Fonctionnel |
| Storage DuckDB | ✅ Fonctionnel (architecture DRY avec héritage) |
| Génération LLM | ✅ Fonctionnel (DI pour testabilité) |
| API FastAPI | ✅ Endpoint generate connecté |
| UI Streamlit | ✅ Génération connectée au backend |
| Packaging .exe | [ ] TODO |

### Prochaines étapes

1. Parser structuré (`raw_text` → `EleveExtraction` complet)
2. Few-shot loader (charger exemples depuis fichiers)
3. Packaging .exe Windows

---

## Sécurité & RGPD

| Aspect | Mesure |
|--------|--------|
| Données élèves | Anonymisées dans le PDF avant envoi cloud |
| Stockage | DuckDB local, pas de cloud |
| Mapping identités | Base séparée (`privacy.duckdb`) |
| OCR cloud | Reçoit uniquement PDFs anonymisés |
| LLM cloud | Reçoit uniquement données pseudonymisées |
| Validation | Obligatoire avant export |

---

## Licence

Projet privé — Usage non commercial.
