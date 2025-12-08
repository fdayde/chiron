# Chiron — Architecture Technique

> Assistant IA pour la préparation des conseils de classe

---

## 1. Vision produit

Outil destiné aux professeurs principaux pour générer des synthèses trimestrielles personnalisées à partir des bulletins scolaires (PDF PRONOTE).

**Workflow** : Import PDF → Extraction structurée → Pseudonymisation → Génération LLM → Validation humaine → Export

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- Données pseudonymisées avant envoi API externe
- Ton et style adaptés via few-shot (exemples du prof)

---

## 2. Structure du projet

```
chiron/
├── src/
│   ├── llm/                 # Abstraction LLM multi-provider
│   │   ├── base.py          # Interface abstraite LLMClient
│   │   ├── manager.py       # Orchestrateur (rate limit, retry, batch)
│   │   ├── config.py        # Settings (clés API, modèles, pricing)
│   │   ├── rate_limiter.py  # Sliding window rate limiter
│   │   ├── metrics.py       # Collecte métriques (tokens, coût, latence)
│   │   ├── pricing.py       # Tables de pricing par provider
│   │   └── clients/
│   │       ├── anthropic.py
│   │       ├── openai.py
│   │       └── mistral.py
│   │
│   ├── document/            # Parsing PDF
│   │   ├── parser.py        # Extraction texte + tableaux (pdfplumber)
│   │   └── bulletin_parser.py  # Parser spécifique bulletins PRONOTE
│   │
│   ├── privacy/             # RGPD
│   │   ├── pseudonymizer.py # Mapping nom↔pseudo, masquage texte
│   │   └── crypto.py        # Chiffrement mapping local (optionnel)
│   │
│   ├── storage/             # Persistance
│   │   ├── db_manager.py    # Accès DuckDB thread-safe
│   │   ├── models.py        # Modèles SQLAlchemy/raw SQL
│   │   └── repositories.py  # CRUD par entité
│   │
│   ├── generation/          # Génération synthèses
│   │   ├── prompt_builder.py   # Construction prompts few-shot
│   │   ├── schemas.py          # Pydantic schemas output LLM
│   │   └── generator.py        # Orchestration génération
│   │
│   ├── api/                 # Backend REST
│   │   ├── main.py          # App FastAPI
│   │   ├── routes/
│   │   │   ├── classes.py
│   │   │   ├── eleves.py
│   │   │   └── export.py
│   │   └── dependencies.py  # Injection dépendances
│   │
│   ├── core/                # Transverse
│   │   ├── constants.py     # Paths, config globale
│   │   ├── logging_config.py
│   │   └── models.py        # Pydantic models partagés
│   │
│   └── utils/
│       └── async_helpers.py # Helpers async/sync
│
├── app/                     # Frontend Streamlit
│   ├── main.py              # Point d'entrée
│   ├── pages/
│   │   ├── 1_import.py      # Import PDF
│   │   ├── 2_review.py      # Review/edit synthèses
│   │   └── 3_export.py      # Export CSV
│   └── components/          # Composants réutilisables
│
├── data/
│   ├── raw/                 # PDFs importés (par classe)
│   ├── db/                  # DuckDB principal
│   │   └── chiron.duckdb
│   ├── mapping/             # Fichiers mapping pseudos (chiffrés)
│   └── exports/             # CSV exportés
│
├── notebooks/               # Dev, tests, exploration
├── tests/
├── scripts/                 # CLI utilities
├── .env                     # Clés API (gitignored)
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 3. Modèle de données (DuckDB)

### Tables principales

```
┌─────────────────┐       ┌─────────────────┐
│     classes     │       │  exemples_prof  │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │───┐   │ id (PK)         │
│ nom             │   │   │ classe_id (FK)  │
│ niveau          │   │   │ eleve_data      │
│ etablissement   │   │   │ synthese_prof   │
│ annee_scolaire  │   │   │ created_at      │
│ created_at      │   │   └─────────────────┘
└─────────────────┘   │
         │            │
         │ 1:N        │ 1:N
         ▼            │
┌─────────────────┐   │
│     eleves      │◄──┘
├─────────────────┤
│ id (PK)         │
│ classe_id (FK)  │───────┐
│ pseudo_id       │       │
│ donnees_json    │       │
│ created_at      │       │
└─────────────────┘       │
         │                │
         │ 1:N            │
         ▼                │
┌─────────────────┐       │
│   syntheses     │       │
├─────────────────┤       │
│ id (PK)         │       │
│ eleve_id (FK)   │◄──────┘
│ trimestre       │
│ status          │  ('draft'|'generated'|'edited'|'validated')
│ synthese_texte  │
│ insights_json   │
│ model_used      │
│ validated_at    │
│ created_at      │
└─────────────────┘
```

### Table mapping (séparée, optionnellement chiffrée)

```
┌─────────────────────┐
│  mapping_identites  │
├─────────────────────┤
│ pseudo_id (PK)      │
│ nom_reel            │
│ prenom_reel         │
│ classe_id           │
└─────────────────────┘
```

---

## 4. Schémas de données (Pydantic)

### Extraction bulletin (input)

```python
class MatiereExtraction(BaseModel):
    nom: str                      # "Mathématiques"
    moyenne_eleve: float | None   # 12.5
    moyenne_classe: float | None  # 13.2
    appreciation: str             # Texte libre

class EleveExtraction(BaseModel):
    nom: str
    prenom: str
    classe: str
    trimestre: int
    matieres: list[MatiereExtraction]
    absences_justifiees: int | None
    absences_injustifiees: int | None
    retards: int | None
    appreciation_generale: str | None  # Si présente sur bulletin
```

### Génération synthèse (output LLM)

```python
class Insight(BaseModel):
    type: Literal["alerte", "reussite", "engagement", "posture", "ecart"]
    description: str
    matieres: list[str] | None = None
    severite: Literal["info", "attention", "urgent"] | None = None

class SyntheseGeneree(BaseModel):
    synthese_texte: str
    alertes: list[Insight]
    reussites: list[Insight]
    engagement_differencie: dict[str, str]  # matière → posture
    posture_generale: Literal["actif", "passif", "perturbateur", "variable"]
    ecart_effort_resultat: Literal["equilibre", "effort_sup_resultat", "resultat_sup_effort"] | None
```

---

## 5. Composants réutilisables depuis Healstra

| Composant | Source Healstra | Adaptation requise |
|-----------|-----------------|-------------------|
| `LLMClient` (base) | `src/llm/base.py` | Aucune |
| `LLMManager` | `src/llm/manager.py` | Aucune |
| `LLMSettings` | `src/llm/config.py` | Adapter defaults |
| `SimpleRateLimiter` | `src/llm/rate_limiter.py` | Aucune |
| `MetricsCollector` | `src/llm/metrics.py` | Aucune |
| Clients (Anthropic, OpenAI, Mistral) | `src/llm/clients/` | Aucune |
| Parser PDF (pdfplumber) | `src/document/parser_v2.py` | Adapter pour tableaux bulletins |
| DB Manager | `src/storage/db_manager.py` | Nouveau schéma |
| Async helpers | `src/utils/async_helpers.py` | Aucune |
| Constants | `src/core/constants.py` | Nouveaux paths |
| Logging | `src/core/logging_config.py` | Aucune |

---

## 6. API REST (FastAPI)

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/classes` | Créer une classe |
| `GET` | `/api/classes` | Lister les classes |
| `GET` | `/api/classes/{id}` | Détail classe |
| `POST` | `/api/classes/{id}/import` | Upload PDF bulletin (multipart) |
| `GET` | `/api/classes/{id}/eleves` | Liste élèves + status synthèses |
| `POST` | `/api/classes/{id}/exemples` | Ajouter exemple few-shot |
| `GET` | `/api/classes/{id}/export` | Export CSV synthèses validées |
| `POST` | `/api/eleves/{id}/generate` | Générer synthèse |
| `GET` | `/api/eleves/{id}/synthese` | Récupérer synthèse courante |
| `PUT` | `/api/eleves/{id}/synthese` | Modifier synthèse |
| `POST` | `/api/eleves/{id}/validate` | Valider synthèse |
| `GET` | `/api/health` | Health check |

### Authentification (MVP)

- Header `X-API-Key` simple pour protéger l'API
- Stocké dans `.env`

---

## 7. Interface Streamlit

### Pages

1. **Import** (`1_import.py`)
   - Sélection/création classe
   - Upload PDF(s) bulletin
   - Prévisualisation extraction
   - Ajout exemples few-shot du prof

2. **Review** (`2_review.py`)
   - Liste élèves avec badges status
   - Vue split : PDF source | Synthèse générée
   - Insights en accordéon (alertes, réussites...)
   - Boutons : Générer / Régénérer / Valider
   - Édition inline textarea

3. **Export** (`3_export.py`)
   - Filtres (classe, trimestre, status)
   - Prévisualisation tableau
   - Export CSV / Copier-coller

### État session

```python
st.session_state:
    - selected_class_id
    - selected_trimestre
    - selected_eleve_id
    - api_base_url
```

---

## 8. Pseudonymisation

### Stratégie

1. **À l'import** : Extraire nom/prénom, générer `pseudo_id` (ex: `ELEVE_001`)
2. **Stockage mapping** : Table séparée ou fichier JSON local (optionnellement chiffré avec Fernet)
3. **Avant appel LLM** : Remplacer toutes occurrences nom/prénom dans texte par pseudo
4. **Après retour LLM** : Ré-identifier dans la synthèse générée

### Patterns à masquer

- Nom, prénom de l'élève
- Noms d'autres élèves mentionnés dans appréciations
- Nom de l'établissement (optionnel)

---

## 9. Prompt Few-Shot

### Structure

```
SYSTEM:
Tu es un assistant pour professeur principal. Tu rédiges des synthèses
trimestrielles pour le conseil de classe.

CONTEXTE CLASSE:
- Niveau : {niveau}
- Effectif : {effectif} élèves
- Trimestre : {trimestre}

EXEMPLES DE SYNTHÈSES (rédigées par le professeur) :

--- Exemple 1 ---
Données élève : {exemple_1_donnees}
Synthèse : {exemple_1_synthese}

--- Exemple 2 ---
...

CONSIGNES :
1. Adopte le même ton et style que les exemples
2. Structure ta réponse en JSON selon le schéma fourni
3. Sois factuel, cite les matières concernées
4. Les alertes doivent être actionnables
...

DONNÉES ÉLÈVE À TRAITER :
{donnees_eleve_pseudo}

Réponds en JSON :
```

---

## 10. Stack technique

| Composant | Technologie |
|-----------|-------------|
| Runtime | Python 3.11+ |
| LLM | OpenAI GPT-4o-mini / Claude Sonnet (via API) |
| Base de données | DuckDB (fichier local) |
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Parsing PDF | pdfplumber |
| Validation données | Pydantic v2 |
| HTTP async | httpx |
| Tests | pytest + pytest-asyncio |
| Packaging | pyproject.toml (hatch/pip) |

---

## 11. Configuration (.env)

```env
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Default model
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini

# API
API_KEY=chiron-secret-key-change-me
API_HOST=0.0.0.0
API_PORT=8000

# Database
DB_PATH=data/db/chiron.duckdb

# Privacy
MAPPING_ENCRYPTION_KEY=...  # Fernet key, optionnel
```

---

## 12. Sécurité & RGPD

| Aspect | Mesure |
|--------|--------|
| Données élèves | Pseudonymisées avant envoi API |
| Stockage local | DuckDB fichier local, pas de cloud |
| Mapping identités | Fichier séparé, optionnellement chiffré |
| Accès API | Clé API en header |
| Logs | Pas de données personnelles dans logs |
| Validation humaine | Obligatoire avant export |
