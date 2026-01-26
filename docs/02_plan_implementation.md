# Chiron — Plan d'implémentation

> Dernière mise à jour : 2026-01-26

---

## Vue d'ensemble

```
Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4 ─► Phase 5 ─► Phase 6 ─► Phase 7
 Setup     Parser     Privacy    Storage    Génération   API       Streamlit   Packaging
           PDF+OCR    +NER       DuckDB     LLM          REST      UI          .exe
```

Chaque phase produit un livrable testable indépendamment.

---

## Légende

- [x] Tâche complétée
- [ ] Tâche à faire
- [~] Tâche partiellement complétée

---

## Phase 0 — Setup projet ✅

### Objectif
Créer la structure du projet et configurer l'environnement.

### Tâches

- [x] **0.1** Créer le repository
- [x] **0.2** Initialiser la structure de dossiers
- [x] **0.3** Créer `pyproject.toml` avec dépendances
- [x] **0.4** Copier/adapter composants LLM (depuis Healstra)
- [x] **0.5** Configurer `src/core/constants.py`
- [x] **0.6** Créer `.env.example` et `.gitignore`
- [x] **0.7** Valider les imports

### Livrable ✅
Projet qui s'installe et importe les modules sans erreur.

---

## Phase 1 — Parser PDF bulletins ✅

### Objectif
Extraire les données d'un PDF bulletin via OCR cloud.

### Tâches

- [x] **1.1** Analyser structure PDF bulletin PRONOTE
- [x] **1.2** Créer `src/document/pdfplumber_parser.py` (extraction locale)
- [x] **1.3** Créer `src/document/mistral_parser.py` (OCR cloud)
- [x] **1.4** Créer factory pattern dans `src/document/__init__.py`
- [x] **1.5** Créer `src/core/models.py` avec schemas Pydantic
- [x] **1.6** Benchmark parsers (notebook `03_parser_benchmark.ipynb`)
- [x] **1.7** Sélectionner Mistral OCR comme parser principal

### Livrable ✅
```python
from src.document import get_parser, ParserType
parser = get_parser(ParserType.MISTRAL_OCR)
eleves = parser.parse("data/raw/bulletin.pdf")
# -> list[EleveExtraction] avec raw_text (markdown)
```

### Note
Le parser retourne actuellement `raw_text` brut. L'extraction structurée (matières, notes) est à faire en Phase 1b.

---

## Phase 1b — Anonymisation PDF (NER) ✅

### Objectif
Anonymiser le PDF **avant** envoi au cloud pour garantir RGPD.

### Tâches

- [x] **1b.1** Tester 3 modèles NER (spaCy, CamemBERT v1, CamemBERTav2)
- [x] **1b.2** Sélectionner CamemBERT v1 (meilleur compromis)
- [x] **1b.3** Implémenter extraction nom (`extract_eleve_name()`)
- [x] **1b.4** Implémenter détection variantes (`detect_name_variants()`)
- [x] **1b.5** Implémenter anonymisation PDF (`anonymize_pdf()` avec PyMuPDF)
- [x] **1b.6** Valider avec Mistral OCR (notebook `05_pdf_anonymization_test.ipynb`)
- [x] **1b.7** Valider flow complet (notebook `04_production_simulation.ipynb`)
- [x] **1b.8** **Intégrer dans `MistralOCRParser`** (anonymisation automatique)
- [x] **1b.9** Créer `src/document/anonymizer.py` (module dédié)

### Livrable ✅
```python
from src.document import get_parser, ParserType

parser = get_parser(ParserType.MISTRAL_OCR)  # anonymize=True par défaut
eleves = parser.parse("bulletin.pdf", eleve_id="ELEVE_001")
# -> Anonymisation automatique avant envoi OCR cloud
# -> eleve._identity contient le mapping nom ↔ eleve_id
```

---

## Phase 1c — Parsing structuré [ ]

### Objectif
Transformer le `raw_text` (markdown OCR) en `EleveExtraction` complet.

### Tâches

- [ ] **1c.1** Parser le markdown pour extraire les matières
- [ ] **1c.2** Extraire notes élève/classe depuis tableaux
- [ ] **1c.3** Extraire appréciations
- [ ] **1c.4** Extraire absences, retards, engagements
- [ ] **1c.5** Valider avec plusieurs formats bulletins

### Livrable
```python
eleves = parser.parse("bulletin.pdf")
# -> EleveExtraction avec matieres[], moyenne_generale, etc.
```

---

## Phase 2 — Pseudonymisation RGPD ✅

### Objectif
Masquer les données personnelles dans les textes et maintenir le mapping.

### Tâches

- [x] **2.1** Créer `src/privacy/pseudonymizer.py`
- [x] **2.2** Implémenter `pseudonymize()` (EleveExtraction → eleve_id)
- [x] **2.3** Implémenter `depseudonymize()` (eleve_id → nom original)
- [x] **2.4** Implémenter `pseudonymize_text()` / `depseudonymize_text()`
- [x] **2.5** Stockage mapping dans DuckDB séparé
- [x] **2.6** Créer `src/privacy/config.py`

### Livrable ✅
```python
from src.privacy.pseudonymizer import Pseudonymizer

pseudo = Pseudonymizer()
eleve_safe = pseudo.pseudonymize(eleve_raw, classe_id="3A")
# eleve_safe.eleve_id = "ELEVE_001", nom=None

original = pseudo.depseudonymize("ELEVE_001")
# {"nom_original": "Dupont", "prenom_original": "Marie"}
```

---

## Phase 3 — Stockage DuckDB ✅

### Objectif
Persistance des classes, élèves, synthèses.

### Tâches

- [x] **3.1** Créer `src/storage/schemas.py` (CREATE TABLE)
- [x] **3.2** Créer `src/storage/connection.py` (singleton thread-safe)
- [x] **3.3** Créer `src/storage/repositories/base.py`
- [x] **3.4** Créer `ClasseRepository`, `EleveRepository`, `SyntheseRepository`
- [x] **3.5** Créer `src/storage/config.py`

### Livrable ✅
```python
from src.storage.connection import get_connection
from src.storage.repositories import EleveRepository

conn = get_connection()
repo = EleveRepository(conn)
repo.create(eleve_data)
eleves = repo.get_by_classe("3A")
```

---

## Phase 4 — Génération LLM ✅

### Objectif
Générer des synthèses avec few-shot learning.

### Tâches

- [x] **4.1** Créer schemas output (`Alerte`, `Reussite`, `SyntheseGeneree`)
- [x] **4.2** Créer `src/generation/prompt_builder.py`
- [x] **4.3** Créer `src/generation/generator.py` (`SyntheseGenerator`)
- [x] **4.4** Intégrer `LLMManager` avec retry et rate limiting
- [x] **4.5** Tester génération (notebook `02_generation_test.ipynb`)

### Améliorations architecture (2026-01-26)

- [x] **4.6** Registry pattern dans `LLMManager` (CLIENT_REGISTRY)
- [x] **4.7** `settings.get_pricing(provider)` centralisé (DRY)
- [x] **4.8** Dependency injection dans `SyntheseGenerator` (testabilité)

### Livrable ✅
```python
from src.generation.generator import SyntheseGenerator

generator = SyntheseGenerator(provider="openai")
generator.set_exemples(exemples_fewshot)
synthese = generator.generate(eleve)
# -> SyntheseGeneree avec texte + alertes + reussites
```

---

## Phase 4b — Few-shot loader [ ]

### Objectif
Charger les exemples few-shot depuis fichiers.

### Tâches

- [ ] **4b.1** Créer format fichier exemples (JSON/YAML)
- [ ] **4b.2** Créer loader `GroundTruthDataset`
- [ ] **4b.3** Intégrer dans `PromptBuilder`
- [ ] **4b.4** Permettre ajout exemples via UI

### Livrable
```python
from src.generation import load_fewshot_examples

exemples = load_fewshot_examples("data/fewshot/3A_T1.json")
generator.set_exemples(exemples)
```

---

## Phase 5 — API REST FastAPI ✅

### Objectif
Exposer les fonctionnalités via API.

### Tâches

- [x] **5.1** Créer `src/api/main.py` (FastAPI + CORS)
- [x] **5.2** Créer `src/api/dependencies.py`
- [x] **5.3** Créer routers CRUD (classes, eleves, syntheses, exports)
- [x] **5.4** Endpoints import PDF
- [x] **5.5** Endpoint export CSV
- [x] **5.6** **Endpoint `/syntheses/generate`**
- [x] **5.7** Connecter endpoint au `SyntheseGenerator`
- [x] **5.8** Injecter `SyntheseGenerator` dans dependencies

### Améliorations architecture (2026-01-26)

- [x] **5.9** Connexions SQL avec context manager `with` partout
- [x] **5.10** `DuckDBRepository` hérite de `DuckDBConnection` (DRY)

### Livrable ✅
```bash
# Tous les endpoints fonctionnent
curl http://localhost:8000/health
curl http://localhost:8000/classes
curl http://localhost:8000/eleves

# Génération LLM réelle
curl -X POST http://localhost:8000/syntheses/generate \
  -H "Content-Type: application/json" \
  -d '{"eleve_id": "ELEVE_001", "trimestre": 1, "provider": "openai"}'
# Retourne synthèse générée via LLM + métadonnées (tokens, prompt_hash, etc.)
```

---

## Phase 6 — Interface Streamlit ✅

### Objectif
Interface utilisateur pour le professeur.

### Tâches

- [x] **6.1** Créer `app/main.py` (config, navigation)
- [x] **6.2** Créer `app/pages/1_import.py` (upload PDF + auto-génération optionnelle)
- [x] **6.3** Créer `app/pages/2_review.py` (review synthèses + paramètres LLM)
- [x] **6.4** Créer `app/pages/3_export.py` (export CSV)
- [x] **6.5** Créer composants (`sidebar`, `eleve_card`, `synthese_editor`)
- [x] **6.6** Créer `app/api_client.py` (avec timeout LLM adapté)
- [x] **6.7** Connecter génération au backend (bouton → API → LLM)
- [x] **6.8** Connecter batch generation avec feedback détaillé

### Livrable ✅
```bash
streamlit run app/main.py
# UI complète :
# - Sélection provider/model/temperature dans sidebar
# - Génération individuelle et batch avec progress bar
# - Auto-génération optionnelle après import
# - Feedback détaillé (tokens, durée, erreurs)
```

---

## Phase 7 — Packaging .exe [ ]

### Objectif
Créer un exécutable Windows autonome.

### Prérequis
- [ ] Toutes les fonctionnalités testées et validées
- [ ] Configuration externalisée
- [ ] Interface Streamlit finalisée

### Tâches

- [ ] **7.1** Choisir outil (PyInstaller vs Nuitka)
- [ ] **7.2** Créer script de build
- [ ] **7.3** Gérer dépendances lourdes (PyTorch, CamemBERT)
- [ ] **7.4** Tester sur machine vierge
- [ ] **7.5** (Optionnel) Créer installateur (NSIS/Inno Setup)

### Estimation taille
| Composant | Taille |
|-----------|--------|
| Python + libs | ~100 MB |
| PyTorch + CamemBERT | ~450 MB |
| Streamlit | ~80 MB |
| **Total** | **~600 MB - 1 GB** |

---

## Mapping : Workflow utilisateur ↔ Phases d'implémentation

Le workflow utilisateur (voir `01_architecture_technique.md` section 5) utilise les composants suivants :

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ WORKFLOW UTILISATEUR                    PHASES UTILISÉES           STATUS       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ 1. Création classe                      Phase 3 (Storage)          ✅          │
│    └─► POST /classes                    Phase 5 (API)              ✅          │
│    └─► ClasseRepository.create()        Phase 6 (UI)               ✅          │
│                                                                                 │
│ 2. Import PDF                           Phase 5 (API)              ✅          │
│    └─► POST /import/pdf                 Phase 6 (UI)               ✅          │
│    └─► Sauvegarde data/raw/                                                    │
│                                                                                 │
│ 3. Anonymisation PDF                    Phase 1b (NER)             ✅          │
│    └─► extract_eleve_name()             Phase 1b.3                 ✅          │
│    └─► detect_name_variants()           Phase 1b.4                 ✅          │
│    └─► anonymize_pdf()                  Phase 1b.5                 ✅          │
│    └─► Stockage mapping                 Phase 2 (Privacy)          ✅          │
│                                                                                 │
│ 4. OCR Cloud                            Phase 1 (Parser)           ✅          │
│    └─► MistralOCRParser.parse()         Phase 1.3                  ✅          │
│    └─► API Mistral OCR                                                         │
│                                                                                 │
│ 5. Parsing structuré                    Phase 1c                   ❌ TODO     │
│    └─► raw_text → EleveExtraction       Phase 1c.1-1c.5            ❌          │
│                                                                                 │
│ 6. Stockage élève                       Phase 3 (Storage)          ✅          │
│    └─► EleveRepository.create()         Phase 3.4                  ✅          │
│    └─► Table eleves (DuckDB)                                                   │
│                                                                                 │
│ 7. Génération synthèse                  Phase 4 (Génération)       ✅          │
│    └─► SyntheseGenerator.generate()     Phase 4.3                  ✅          │
│    └─► PromptBuilder (few-shot)         Phase 4.2                  ✅          │
│    └─► LLMManager.call()                Phase 4.4                  ✅          │
│    └─► API endpoint                     Phase 5.6-5.8              ✅          │
│    └─► UI bouton "Générer"              Phase 6.7-6.8              ✅          │
│                                                                                 │
│ 8. Validation utilisateur               Phase 5 (API)              ✅          │
│    └─► PATCH /syntheses/{id}            Phase 5.3                  ✅          │
│    └─► POST /syntheses/{id}/validate                               ✅          │
│    └─► UI édition/validation            Phase 6.3                  ✅          │
│                                                                                 │
│ 9. Export CSV                           Phase 5 (API)              ✅          │
│    └─► GET /export/csv                  Phase 5.5                  ✅          │
│    └─► Pseudonymizer.depseudonymize()   Phase 2.4                  ✅          │
│    └─► UI export                        Phase 6.4                  ✅          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Points de blocage dans le workflow

| Étape workflow | Bloqué par | Action requise |
|----------------|------------|----------------|
| ~~**3 → 4**~~ | ~~Phase 1b non intégrée~~ | ✅ Fait - Anonymisation intégrée |
| **4 → 5** | Phase 1c non faite | Parser markdown → `EleveExtraction` structuré |
| ~~**6 → 7**~~ | ~~Phase 5.7-5.8 non faite~~ | ✅ Fait - Endpoint connecté au `SyntheseGenerator` |
| ~~**UI → 7**~~ | ~~Phase 6.7-6.8 non faite~~ | ✅ Fait - UI connectée au backend |

### Chemin critique pour un workflow fonctionnel

```
Pour que le workflow soit 100% opérationnel :

    ┌─────────────────────────────────────────────────────────────────┐
    │ MINIMUM VIABLE (workflow complet fonctionnel)        ✅ FAIT    │
    ├─────────────────────────────────────────────────────────────────┤
    │ ✅ Phase 5.7-5.8 : Connecter /syntheses/generate                │
    │    → FAIT - Génération via API fonctionnelle                    │
    │                                                                 │
    │ ✅ Phase 6.7-6.8 : Connecter UI au backend                      │
    │    → FAIT - Génération via interface Streamlit                  │
    │    → Paramètres LLM (provider/model/temperature)                │
    │    → Batch generation avec progress bar                         │
    │    → Auto-génération optionnelle après import                   │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │ AMÉLIORATIONS (production-ready)                                │
    ├─────────────────────────────────────────────────────────────────┤
    │ ✅ Phase 1b.8-1b.9 : Intégrer anonymisation                     │
    │    → FAIT - Anonymisation automatique dans MistralOCRParser     │
    │                                                                 │
    │ 1. Phase 1c : Parsing structuré                                 │
    │    → Données structurées (matieres[], notes) au lieu de raw_text│
    │                                                                 │
    │ 2. Phase 4b : Few-shot loader                                   │
    │    → Charger exemples depuis fichiers                           │
    └─────────────────────────────────────────────────────────────────┘
```

---

## Résumé status

| Phase | Nom | Status |
|-------|-----|--------|
| 0 | Setup | ✅ Complet |
| 1 | Parser PDF | ✅ Complet |
| 1b | Anonymisation NER | ✅ Complet (intégré dans MistralOCRParser) |
| 1c | Parsing structuré | [ ] TODO |
| 2 | Privacy | ✅ Complet |
| 3 | Storage | ✅ Complet (schéma mis à jour avec métadonnées LLM) |
| 4 | Génération LLM | ✅ Complet |
| 4b | Few-shot loader | [ ] TODO |
| 5 | API REST | ✅ Complet (endpoint /syntheses/generate connecté) |
| 6 | Streamlit | ✅ Complet (génération connectée + paramètres LLM) |
| 7 | Packaging | [ ] TODO |

---

## Prochaines étapes prioritaires

1. ~~**Connecter `/syntheses/generate`** au `SyntheseGenerator` (Phase 5.7-5.8)~~ ✅ Fait
2. ~~**Connecter UI** génération au backend (Phase 6.7-6.8)~~ ✅ Fait
3. **Parser structuré** : `raw_text` → `EleveExtraction` complet (Phase 1c)
4. **Few-shot loader** : charger exemples depuis fichiers (Phase 4b)
5. **Packaging** : créer exécutable Windows (Phase 7)

---

## Risques et mitigations

| Risque | Mitigation |
|--------|------------|
| Format PDF variable | Parser flexible, tester sur plusieurs établissements |
| Qualité synthèses | Itérer prompts, ajuster few-shot |
| Noms non détectés | CamemBERT NER + liste exhaustive noms classe |
| Performance (latence) | Async, feedback loading UI |
| Coût API | Caching, batch, modèle économique (gpt-4o-mini) |
| Taille .exe | Optimiser dépendances, ONNX pour CamemBERT |

---

## Notebooks de validation

| Notebook | Status | Description |
|----------|--------|-------------|
| `01_parser_dev.ipynb` | ✅ | Développement parsers |
| `02_generation_test.ipynb` | ✅ | Test génération LLM |
| `03_parser_benchmark.ipynb` | ✅ | Comparaison parsers (Docling, Mistral OCR) |
| `04_production_simulation.ipynb` | ✅ | Simulation workflow complet |
| `05_pdf_anonymization_test.ipynb` | ✅ | Test anonymisation PDF + NER |
| `06_workflow_complet.ipynb` | ✅ | Workflow end-to-end avec estimation coûts |
