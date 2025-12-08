# Chiron

> Assistant IA pour la préparation des conseils de classe

---

## Description

Chiron est un outil destiné aux professeurs principaux pour générer des synthèses trimestrielles personnalisées à partir des bulletins scolaires (PDF PRONOTE).

**Workflow** :
1. Import des PDF bulletins
2. Extraction automatique des données (notes, appréciations)
3. Pseudonymisation des données personnelles (RGPD)
4. Génération de synthèses par LLM (style adapté via few-shot)
5. Validation/édition par le professeur
6. Export pour le conseil de classe

**Principes** :
- Le professeur reste dans la boucle (validation obligatoire)
- Données pseudonymisées avant tout envoi API externe
- Style et ton personnalisés via exemples du professeur

---

## Stack technique

- **Python 3.11+**
- **LLM** : OpenAI GPT-4o-mini / Claude (API externe)
- **Backend** : FastAPI
- **Frontend** : Streamlit
- **Base de données** : DuckDB (local)
- **Parsing PDF** : pdfplumber

---

## Installation

```bash
# Cloner le repo
git clone https://github.com/[user]/chiron.git
cd chiron

# Créer environnement virtuel
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows

# Installer dépendances
pip install -e .

# Configurer
cp .env.example .env
# Éditer .env avec vos clés API
```

---

## Configuration (.env)

```env
# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...  # optionnel
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini

# API
API_KEY=chiron-secret-key
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
python scripts/run_api.py

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
│   ├── document/         # Parsing PDF bulletins
│   ├── privacy/          # Pseudonymisation RGPD
│   ├── storage/          # DuckDB
│   ├── generation/       # Prompts et génération synthèses
│   ├── api/              # FastAPI routes
│   └── core/             # Config, models, utils
├── app/                  # Streamlit frontend
│   ├── main.py
│   └── pages/
├── data/
│   ├── raw/              # PDFs importés
│   ├── db/               # DuckDB
│   └── exports/          # CSV
├── notebooks/            # Dev notebooks
├── tests/
└── scripts/
```

---

## Documentation technique

Voir les documents de référence :
- `docs/01_architecture_technique.md` — Architecture détaillée
- `docs/02_plan_implementation.md` — Plan d'implémentation par phases

---

## Projet de référence

Ce projet s'inspire de l'architecture de **Healstra** (extraction d'informations médicales), dont les composants suivants sont réutilisés :

| Composant | Source |
|-----------|--------|
| Abstraction LLM | `src/llm/*` |
| Rate limiting | `src/llm/rate_limiter.py` |
| Métriques | `src/llm/metrics.py` |
| Parser PDF | `src/document/parser_v2.py` |
| Async helpers | `src/utils/async_helpers.py` |

Chemin du projet Healstra de référence :
```
C:/Users/Florent/Documents/data_science_missions/Healstra/healstra-beonemed-avisct/
```

---

## Licence

Projet privé — Usage non commercial.

---

# INSTRUCTIONS POUR CLAUDE CODE

> Cette section sert de contexte pour démarrer une nouvelle session de développement.

## Contexte projet

Tu travailles sur **Chiron**, un assistant IA pour professeurs principaux.

**Objectif** : À partir de PDF de bulletins scolaires PRONOTE, générer des synthèses trimestrielles personnalisées avec insights (alertes, réussites, engagement...).

**Architecture** : Backend FastAPI + Frontend Streamlit + DuckDB local + LLM externe (OpenAI/Claude).

**Contrainte RGPD** : Les données élèves doivent être pseudonymisées avant envoi au LLM.

## Projet de référence à consulter

Le projet **Healstra** contient des composants réutilisables :
```
C:/Users/Florent/Documents/data_science_missions/Healstra/healstra-beonemed-avisct/
```

Composants à copier/adapter :
- `src/llm/` — Abstraction LLM complète (multi-provider, rate limiting, retry)
- `src/document/parser_v2.py` — Parser PDF avec pdfplumber
- `src/storage/db_manager.py` — Gestion DuckDB thread-safe
- `src/utils/async_helpers.py` — Helpers async
- `src/core/constants.py`, `logging_config.py` — Config

## Documentation de référence

Consulter ces fichiers pour l'architecture et le plan détaillé :
- `docs/chiron/01_architecture_technique.md`
- `docs/chiron/02_plan_implementation.md`

## Format bulletins

- PDF PRONOTE standardisé
- Tableau 3 colonnes (Matière | Note | Appréciation)
- ~30 élèves par classe
- Multi-classes, multi-trimestres

## Outputs attendus par élève

```python
class SyntheseGeneree(BaseModel):
    synthese_texte: str              # Rédigée dans le ton du prof
    alertes: list[Insight]           # Notes < 8, décrochage
    reussites: list[Insight]         # Points forts
    engagement_differencie: dict     # matière → posture
    posture_generale: str            # actif|passif|perturbateur|variable
    ecart_effort_resultat: str       # equilibre|effort>resultat|resultat>effort
```

## Priorités MVP

1. Parser PDF fonctionnel sur bulletins réels
2. Pseudonymisation robuste
3. Génération synthèses avec few-shot
4. Interface Streamlit minimaliste mais fonctionnelle
5. Export CSV

## Comment démarrer

1. Lire les docs de référence (`docs/chiron/`)
2. Créer la structure du projet
3. Copier les composants réutilisables depuis Healstra
4. Suivre le plan d'implémentation phase par phase
5. Demander un exemple PDF bulletin pour développer le parser

## Questions fréquentes

**Q: Où stocker le mapping de pseudonymisation ?**
A: Table DuckDB séparée ou fichier JSON local (optionnellement chiffré).

**Q: Quel LLM utiliser ?**
A: GPT-4o-mini par défaut (bon rapport qualité/coût). Claude en fallback.

**Q: Comment personnaliser le style des synthèses ?**
A: Few-shot avec 2-3 exemples de synthèses rédigées par le prof, stockées en DB.

**Q: Format d'export ?**
A: CSV avec colonnes : Élève, Synthèse, Alertes, Réussites, Status, Date validation.
