# Chiron - Suivi d'avancement

> Dernière mise à jour : 2026-01-23

---

## ✅ FAIT (Complet)

| Phase | Composant | Détails |
|-------|-----------|---------|
| 0 | Setup | Structure, dépendances, config |
| 1 | Parser PDF | 2 implémentations (pdfplumber + Mistral OCR) |
| 2 | Privacy | Pseudonymisation avec mapping DuckDB |
| 3 | Storage | DuckDB + 4 repositories (Classe, Eleve, Synthese, Mapping) |
| 4 | Generation | `SyntheseGenerator` + `PromptBuilder` (classes créées) |
| 5 | API | Tous les endpoints CRUD définis |
| 6 | UI Import | Upload PDF + parsing |
| 6 | UI Export | Export CSV fonctionnel |

### Détails par module

- **`src/document/`** : Factory pattern, `PdfplumberParser`, `MistralOCRParser`, estimation coût
- **`src/privacy/`** : `Pseudonymizer` avec stockage DuckDB, pseudonymize/depseudonymize text
- **`src/storage/`** : Connection singleton, repositories CRUD, schemas SQL
- **`src/generation/`** : `PromptBuilder` (few-shot, system prompt), `SyntheseGenerator` (generate, generate_batch)
- **`src/api/`** : FastAPI avec routers (classes, eleves, syntheses, exports)
- **`app/`** : Streamlit avec pages (import, review, export) et composants

---

## ⚠️ PARTIEL (À connecter)

| Composant | Problème | Fichier |
|-----------|----------|---------|
| **API /syntheses/generate** | Endpoint existe mais retourne placeholder, pas connecté au `SyntheseGenerator` | `src/api/routers/syntheses.py` |
| **Parser → EleveExtraction** | Retourne `raw_text`/`raw_tables` mais pas les champs structurés (matières, notes) | `src/document/pdfplumber_parser.py` |
| **UI Review** | Layout fait, mais génération pas connectée au backend | `app/pages/2_review.py` |
| **Few-shot examples** | Models définis mais pas de mécanisme pour charger les exemples | `src/generation/` |

---

## 🔴 TODO (Pas commencé)

### Priorité haute

- [ ] **Intégrer anonymisation PDF dans MistralOCRParser**
  - Testé dans `notebooks/05_pdf_anonymization_test.ipynb` ✅
  - À intégrer dans `src/document/mistral_parser.py`
  - Utiliser CamemBERT NER (`Jean-Baptiste/camembert-ner`) pour détecter les noms
  - Anonymiser avec PyMuPDF avant envoi à Mistral OCR

- [ ] **Connecter endpoint génération au SyntheseGenerator**
  - Fichier : `src/api/routers/syntheses.py`
  - Injecter `SyntheseGenerator` dans les dépendances
  - Appeler `generator.generate()` au lieu du placeholder

- [ ] **Parser données brutes en EleveExtraction structuré**
  - Extraire : nom, classe, trimestre, matières, notes, appréciations
  - Depuis `raw_text` et `raw_tables`
  - Possibilité d'utiliser LLM pour extraction structurée

### Priorité moyenne

- [ ] **Tester NiceGUI comme alternative à Streamlit**
  - Plus réactif (pas de rerun complet)
  - Mode `native=True` pour app desktop
  - Packaging PyInstaller OK
  - POC : recréer la page d'import en NiceGUI
  - `uv add nicegui`

- [ ] **Charger exemples few-shot depuis ground truth**
  - Créer repository ou loader pour `GroundTruthDataset`
  - Intégrer dans `PromptBuilder`

- [ ] **Batch generation fonctionnel**
  - Connecter bouton UI au backend
  - Utiliser `generator.generate_batch()`

- [ ] **Tests unitaires**
  - Couverture actuelle faible
  - Priorité : parser, pseudonymizer, generator

### Priorité basse

- [ ] **README** complet avec screenshots
- [ ] **Logging structuré** pour debug

---

## 📦 Packaging .exe (Phase finale)

### Prérequis avant packaging
- [ ] Toutes les fonctionnalités testées et validées
- [ ] Configuration externalisée (clés API dans fichier config local)
- [ ] Interface Streamlit finalisée

### Tâches packaging
- [ ] **Choisir l'outil de packaging**
  - Option 1 : PyInstaller (plus mature, communauté large)
  - Option 2 : Nuitka (compilation native, plus rapide au runtime)

- [ ] **Créer script de build**
  - `scripts/build_exe.py` ou `build.spec` (PyInstaller)
  - Inclure tous les assets (modèles, templates)

- [ ] **Gérer les dépendances lourdes**
  - PyTorch + CamemBERT : inclure dans le bundle
  - Alternative : convertir en ONNX pour réduire la taille

- [ ] **Tester sur machine "vierge"**
  - VM Windows sans Python
  - Vérifier que tout fonctionne

- [ ] **Créer installateur** (optionnel)
  - NSIS ou Inno Setup pour un .exe d'installation propre
  - Raccourci bureau, désinstallation propre

### Estimation taille finale
| Composant | Taille |
|-----------|--------|
| Python + libs | ~100 MB |
| PyTorch | ~450 MB |
| CamemBERT model | ~400 MB |
| Streamlit + UI | ~80 MB |
| **Total** | **~600 MB - 1 GB**

---

## Notebooks de validation

| Notebook | Status | Description |
|----------|--------|-------------|
| `01_parser_dev.ipynb` | ✅ | Test des parsers |
| `02_generation_test.ipynb` | ✅ | Test génération LLM |
| `03_parser_benchmark.ipynb` | ✅ | Comparaison parsers |
| `04_production_simulation.ipynb` | ✅ | Simulation workflow |
| `05_pdf_anonymization_test.ipynb` | ✅ | Test anonymisation PDF + NER |

---

## Flow principal

```
PDF original
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. Extraction nom (pdfplumber + regex)      │ ✅
│ 2. NER pour variantes (CamemBERT)           │ ✅
│ 3. Anonymisation PDF (PyMuPDF redaction)    │ ✅
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 4. OCR (Mistral OCR ou pdfplumber)          │ ✅
│ 5. Parsing structuré → EleveExtraction      │ ⚠️ PARTIEL
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 6. Stockage DuckDB (pseudonymisé)           │ ✅
│ 7. Génération synthèse (LLM + few-shot)     │ ⚠️ API non connectée
│ 8. Validation par utilisateur               │ ✅ UI existe
│ 9. Export CSV (dépseudonymisé)              │ ✅
└─────────────────────────────────────────────┘
```

---

## Décisions techniques

| Sujet | Décision | Date |
|-------|----------|------|
| **Architecture** | App locale .exe + APIs cloud (OCR, LLM) | 2026-01-23 |
| **Frontend** | Streamlit (actuel) → Tester NiceGUI (plus réactif) | 2026-01-23 |
| Parser PDF | Mistral OCR (meilleure précision) | 2026-01-23 |
| NER français | CamemBERT v1 (`Jean-Baptiste/camembert-ner`) - meilleur compromis | 2026-01-23 |
| Anonymisation | PyMuPDF redaction avant envoi cloud | 2026-01-23 |
| Stockage | DuckDB (léger, SQL, pas de serveur) | - |
| LLM | Configurable (OpenAI, Anthropic, Mistral) | - |

---

## Architecture de déploiement

```
┌─────────────────────────────────────────────────────────────────────┐
│                      APP LOCALE (.exe ~600MB)                       │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ pdfplumber      │  │ CamemBERT NER   │  │ PyMuPDF             │ │
│  │ (extraction)    │  │ (variantes nom) │  │ (anonymisation)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ DuckDB          │  │ Streamlit UI    │  │ Mapping local       │ │
│  │ (stockage)      │  │ (interface)     │  │ (ELEVE_ID ↔ nom)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ PDF anonymisé uniquement
                                   ▼
              ┌─────────────────────────────────────────┐
              │            CLOUD (APIs)                 │
              │  ┌─────────────┐  ┌─────────────────┐  │
              │  │ Mistral OCR │  │ LLM (OpenAI,    │  │
              │  │             │  │ Anthropic, etc) │  │
              │  └─────────────┘  └─────────────────┘  │
              └─────────────────────────────────────────┘
```

**Avantages :**
- RGPD OK : données personnelles jamais envoyées au cloud (anonymisées avant)
- Mapping nom ↔ ID reste en local sur PC du prof
- Persistance et historique possibles
- Mises à jour faciles (seules les APIs changent côté cloud)

**Composants locaux (~600 MB) :**
| Composant | Taille |
|-----------|--------|
| Python runtime | ~30 MB |
| PyTorch + CamemBERT | ~450 MB |
| pdfplumber, PyMuPDF | ~20 MB |
| Streamlit | ~80 MB |
| DuckDB | ~10 MB |
