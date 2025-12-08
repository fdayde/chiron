# Chiron — Plan d'implémentation

---

## Vue d'ensemble

```
Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4 ─► Phase 5 ─► Phase 6
 Setup     Parser     Privacy    Storage    Génération   API       Streamlit
           PDF                   DuckDB     LLM          REST      UI
```

Chaque phase produit un livrable testable indépendamment.

---

## Phase 0 — Setup projet

### Objectif
Créer la structure du projet et copier les composants réutilisables de Healstra.

### Tâches

- [ ] **0.1** Créer le repository GitHub `chiron`
- [ ] **0.2** Initialiser la structure de dossiers
  ```
  mkdir -p src/{llm,document,privacy,storage,generation,api,core,utils}
  mkdir -p app/pages data/{raw,db,mapping,exports} notebooks tests scripts
  ```
- [ ] **0.3** Créer `pyproject.toml` avec dépendances :
  ```toml
  [project]
  name = "chiron"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = [
      "anthropic>=0.40.0",
      "openai>=1.50.0",
      "httpx>=0.27.0",
      "pydantic>=2.9.0",
      "pydantic-settings>=2.5.0",
      "duckdb>=1.1.0",
      "pdfplumber>=0.11.0",
      "fastapi>=0.115.0",
      "uvicorn>=0.32.0",
      "streamlit>=1.40.0",
      "python-multipart>=0.0.12",
      "tenacity>=9.0.0",
      "python-dotenv>=1.0.0",
  ]
  ```
- [ ] **0.4** Copier depuis Healstra :
  - `src/llm/` (complet)
  - `src/utils/async_helpers.py`
  - `src/core/logging_config.py`
- [ ] **0.5** Adapter `src/core/constants.py` pour Chiron
- [ ] **0.6** Créer `.env.example` et `.gitignore`
- [ ] **0.7** Créer notebook `notebooks/00_setup_test.ipynb` pour valider les imports

### Livrable
Projet qui s'installe (`pip install -e .`) et importe `src.llm.manager` sans erreur.

---

## Phase 1 — Parser PDF bulletins

### Objectif
Extraire les données structurées d'un PDF bulletin PRONOTE (tableau 3 colonnes).

### Tâches

- [ ] **1.1** Analyser un exemple PDF bulletin :
  - Identifier structure tableau (headers, colonnes)
  - Repérer zones : infos élève, matières, absences, appréciations
- [ ] **1.2** Créer `src/document/parser.py` :
  - Fonction `extract_tables(pdf_path)` avec pdfplumber
  - Fonction `clean_text(text)` pour normalisation
- [ ] **1.3** Créer `src/document/bulletin_parser.py` :
  - Classe `BulletinParser`
  - Méthode `parse(pdf_path) -> list[EleveExtraction]`
  - Gestion multi-élèves si plusieurs par PDF
- [ ] **1.4** Créer `src/core/models.py` avec schemas Pydantic :
  - `MatiereExtraction`
  - `EleveExtraction`
- [ ] **1.5** Créer notebook `notebooks/01_parser_dev.ipynb` :
  - Tests sur PDF réel
  - Validation extraction
  - Edge cases (notes manquantes, appréciations vides)
- [ ] **1.6** Écrire tests unitaires `tests/test_bulletin_parser.py`

### Livrable
```python
from src.document.bulletin_parser import BulletinParser
parser = BulletinParser()
eleves = parser.parse("data/raw/bulletin_3A_T1.pdf")
# -> list[EleveExtraction] avec toutes les données structurées
```

---

## Phase 2 — Pseudonymisation RGPD

### Objectif
Masquer les données personnelles avant envoi au LLM, pouvoir ré-identifier après.

### Tâches

- [ ] **2.1** Créer `src/privacy/pseudonymizer.py` :
  - Classe `Pseudonymizer`
  - Méthode `register(nom, prenom, classe_id) -> pseudo_id`
  - Méthode `pseudonymize_text(text) -> text_pseudo`
  - Méthode `depseudonymize_text(text_pseudo) -> text_original`
- [ ] **2.2** Implémenter stockage mapping :
  - Option A : Table DuckDB séparée
  - Option B : Fichier JSON local
  - Méthode `save_mapping()` / `load_mapping()`
- [ ] **2.3** (Optionnel) Créer `src/privacy/crypto.py` :
  - Chiffrement Fernet du fichier mapping
  - Clé dans `.env`
- [ ] **2.4** Patterns de détection :
  - Regex pour noms propres dans appréciations
  - Liste des noms de la classe pour matching
- [ ] **2.5** Créer notebook `notebooks/02_privacy_test.ipynb`
- [ ] **2.6** Tests unitaires `tests/test_pseudonymizer.py`

### Livrable
```python
from src.privacy.pseudonymizer import Pseudonymizer
pseudo = Pseudonymizer(classe_id="3A")
pseudo.register("Dupont", "Marie")  # -> "ELEVE_001"
text_safe = pseudo.pseudonymize_text("Marie Dupont est sérieuse")
# -> "ELEVE_001 est sérieuse"
text_original = pseudo.depseudonymize_text(text_safe)
# -> "Marie Dupont est sérieuse"
```

---

## Phase 3 — Stockage DuckDB

### Objectif
Persistance des classes, élèves, synthèses et exemples few-shot.

### Tâches

- [ ] **3.1** Créer `src/storage/models.py` :
  - Définition des tables SQL (CREATE TABLE)
  - Index et contraintes
- [ ] **3.2** Créer `src/storage/db_manager.py` :
  - Classe `DBManager` (singleton, thread-safe)
  - Méthode `init_db()` pour création tables
  - Connection pooling simple
- [ ] **3.3** Créer `src/storage/repositories.py` :
  - `ClasseRepository` : CRUD classes
  - `EleveRepository` : CRUD élèves
  - `SyntheseRepository` : CRUD synthèses
  - `ExempleRepository` : CRUD exemples few-shot
- [ ] **3.4** Méthodes spécifiques :
  - `get_eleves_by_classe(classe_id, trimestre)`
  - `get_syntheses_by_status(classe_id, status)`
  - `get_exemples_fewshot(classe_id, limit=3)`
- [ ] **3.5** Notebook `notebooks/03_storage_test.ipynb`
- [ ] **3.6** Tests `tests/test_repositories.py`

### Livrable
```python
from src.storage.db_manager import DBManager
from src.storage.repositories import EleveRepository

db = DBManager("data/db/chiron.duckdb")
db.init_db()
repo = EleveRepository(db)
repo.create(eleve_data)
eleves = repo.get_by_classe("3A", trimestre=1)
```

---

## Phase 4 — Génération LLM

### Objectif
Générer des synthèses avec few-shot learning dans le style du professeur.

### Tâches

- [ ] **4.1** Créer `src/generation/schemas.py` :
  - `Insight` (Pydantic)
  - `SyntheseGeneree` (Pydantic)
- [ ] **4.2** Créer `src/generation/prompt_builder.py` :
  - Classe `PromptBuilder`
  - Template système avec consignes
  - Injection exemples few-shot
  - Injection contexte classe
  - Injection données élève (pseudonymisées)
- [ ] **4.3** Créer `src/generation/generator.py` :
  - Classe `SyntheseGenerator`
  - Méthode `generate(eleve_id, trimestre) -> SyntheseGeneree`
  - Orchestration : récup données → pseudo → prompt → LLM → dépseudo → save
- [ ] **4.4** Intégrer `LLMManager` de healstra :
  - Config provider/model par défaut
  - JSON parsing automatique
  - Retry sur erreurs
- [ ] **4.5** Notebook `notebooks/04_generation_test.ipynb` :
  - Test end-to-end sur élève fictif
  - Validation qualité output
  - Ajustement prompt
- [ ] **4.6** Tests `tests/test_generator.py`

### Livrable
```python
from src.generation.generator import SyntheseGenerator

generator = SyntheseGenerator(db_manager, llm_manager, pseudonymizer)
synthese = await generator.generate(eleve_id="...", trimestre=1)
# -> SyntheseGeneree avec texte + insights
```

---

## Phase 5 — API REST FastAPI

### Objectif
Exposer les fonctionnalités via API pour découplage front/back.

### Tâches

- [ ] **5.1** Créer `src/api/main.py` :
  - App FastAPI
  - CORS middleware
  - Exception handlers
- [ ] **5.2** Créer `src/api/dependencies.py` :
  - Injection `DBManager`
  - Injection `LLMManager`
  - Vérification API key
- [ ] **5.3** Créer `src/api/routes/classes.py` :
  - `POST /api/classes`
  - `GET /api/classes`
  - `GET /api/classes/{id}`
  - `POST /api/classes/{id}/import` (upload PDF)
  - `POST /api/classes/{id}/exemples`
  - `GET /api/classes/{id}/export`
- [ ] **5.4** Créer `src/api/routes/eleves.py` :
  - `GET /api/classes/{id}/eleves`
  - `POST /api/eleves/{id}/generate`
  - `GET /api/eleves/{id}/synthese`
  - `PUT /api/eleves/{id}/synthese`
  - `POST /api/eleves/{id}/validate`
- [ ] **5.5** Créer `src/api/routes/health.py` :
  - `GET /api/health`
- [ ] **5.6** Créer `scripts/run_api.py` :
  ```python
  uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
  ```
- [ ] **5.7** Tests `tests/test_api.py` avec TestClient

### Livrable
API fonctionnelle testable via curl/Postman :
```bash
curl -X POST http://localhost:8000/api/classes \
  -H "X-API-Key: ..." \
  -d '{"nom": "3ème A", "niveau": "3ème"}'
```

---

## Phase 6 — Interface Streamlit

### Objectif
Interface utilisateur pour le professeur principal.

### Tâches

- [ ] **6.1** Créer `app/main.py` :
  - Config page (titre, layout)
  - Sidebar navigation
  - Session state init
- [ ] **6.2** Créer `app/pages/1_import.py` :
  - Formulaire création classe
  - File uploader PDF
  - Prévisualisation extraction (tableau)
  - Zone ajout exemples few-shot (2 textareas : données + synthèse)
- [ ] **6.3** Créer `app/pages/2_review.py` :
  - Sélecteur classe / trimestre
  - Liste élèves avec badges status (st.dataframe ou cards)
  - Vue split : col1 = données élève, col2 = synthèse
  - Accordéon insights (alertes, réussites...)
  - Textarea édition synthèse
  - Boutons : Générer / Régénérer / Valider
- [ ] **6.4** Créer `app/pages/3_export.py` :
  - Filtres (classe, trimestre, status)
  - Preview tableau final
  - Bouton export CSV
  - Bouton copier dans presse-papier
- [ ] **6.5** Créer `app/components/` si nécessaire :
  - `eleve_card.py`
  - `synthese_editor.py`
- [ ] **6.6** Connecter au backend :
  - Appels API via `httpx` ou `requests`
  - Gestion erreurs et loading states
- [ ] **6.7** Créer `scripts/run_app.py` :
  ```bash
  streamlit run app/main.py
  ```

### Livrable
Interface complète :
```bash
# Terminal 1
python scripts/run_api.py

# Terminal 2
streamlit run app/main.py
```

---

## Phase 7 — Polish & Documentation (optionnel MVP+)

### Tâches

- [ ] **7.1** README complet avec :
  - Installation
  - Configuration
  - Usage
  - Screenshots
- [ ] **7.2** Tests supplémentaires (coverage > 70%)
- [ ] **7.3** Dockerfile pour déploiement facile
- [ ] **7.4** Script `scripts/setup.py` pour init DB + config
- [ ] **7.5** Gestion erreurs UX (messages clairs dans Streamlit)
- [ ] **7.6** Logging structuré pour debug

---

## Dépendances entre phases

```
Phase 0 (Setup)
    │
    ▼
Phase 1 (Parser) ──────────────────┐
    │                              │
    ▼                              │
Phase 2 (Privacy) ◄────────────────┤
    │                              │
    ▼                              │
Phase 3 (Storage) ◄────────────────┘
    │
    ▼
Phase 4 (Génération)
    │
    ▼
Phase 5 (API)
    │
    ▼
Phase 6 (Streamlit)
```

**Note** : Les phases 1, 2, 3 peuvent être développées en parallèle partiellement.

---

## Points de validation

| Phase | Test de validation |
|-------|-------------------|
| 0 | `from src.llm.manager import LLMManager` fonctionne |
| 1 | Parser extrait correctement un PDF bulletin réel |
| 2 | Texte pseudonymisé ne contient plus de noms réels |
| 3 | CRUD complet fonctionne, données persistées |
| 4 | Synthèse générée cohérente, JSON valide |
| 5 | Tous endpoints répondent correctement (Postman/curl) |
| 6 | Workflow complet : import → génération → validation → export |

---

## Risques identifiés

| Risque | Mitigation |
|--------|------------|
| Format PDF variable selon établissements | Parser flexible, tests sur plusieurs exemples |
| Qualité synthèses LLM insuffisante | Itérer sur prompts, ajuster few-shot |
| Noms non détectés dans appréciations | Regex + liste exhaustive noms classe |
| Performance (latence LLM) | Async, feedback loading dans UI |
| Coût API si beaucoup d'élèves | Caching, batch, modèle économique (gpt-4o-mini) |
