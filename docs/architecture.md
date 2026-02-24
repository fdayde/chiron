# Architecture Chiron

## Flux d'import PDF

```
PDF
 │
 ▼
┌─────────────────────────────────────┐
│ 1. extract_eleve_name()             │  anonymizer.py (regex local)
│    → nom, prénom, genre             │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 2. pseudonymizer.create_eleve_id()  │  Stocke mapping dans privacy.duckdb
│    → "ELEVE_001"                    │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 3. get_parser().parse()             │  yaml_template (défaut) ou pdfplumber
│    → EleveExtraction                │  configurable via PDF_PARSER_TYPE
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 4. validate_extraction()            │  Validation post-extraction
│    + check_classe_mismatch()        │  Erreurs bloquantes + warnings
│    → ValidationResult               │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 5. _pseudonymize_extraction()       │  Pipeline 3 passes (regex + Flair NER
│    → textes avec noms remplacés     │  + fuzzy) sur les appréciations
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 6. eleve_repo.create()              │  Stocke dans chiron.duckdb
└─────────────────────────────────────┘   PK composite: (eleve_id, classe_id, trimestre)
```

## Flux de génération

```
EleveExtraction
 │
 ▼
┌─────────────────────────────────────┐
│ 1. prompt_builder.format_eleve_data │  Formate les données élève
│    → texte structuré                │  (absences, notes, appréciations)
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 2. get_fewshot_examples()           │  Charge 0-3 exemples validés
│    + build_fewshot_examples()       │  (is_fewshot_example = TRUE)
│    → exemples re-pseudonymisés      │  Appréciations: 1ère phrase
│                                     │  Synthèse: max 1000 car.
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 3. prompts.get_prompt("synthese_v3")│  Prompt fondé sur recherche :
│    → system + user prompts          │  growth mindset, feedforward,
│                                     │  SDT, détection biais genre
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 4. LLMManager → LLMClient._do_call │  OpenAI / Anthropic / Mistral
│    → JSON (synthèse, alertes,       │  Retry, rate limiting, metrics
│       réussites, stratégies, biais) │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 5. depseudonymize_text()            │  ELEVE_XXX → prénom réel
│    + synthese_repo.create()         │  Stocke dans chiron.duckdb
└─────────────────────────────────────┘
```

## Flux d'export

```
synthese_repo.get_validated() → pseudonymizer.depseudonymize_text() → Presse-papiers (noms réels)
```

## Composants

### Parsing PDF

| Fichier | Responsabilité |
|---------|----------------|
| `src/document/__init__.py` | Factory `get_parser()`, `PDFParser` Protocol |
| `src/document/anonymizer.py` | `extract_eleve_name()` |
| `src/document/pseudonymization.py` | Pipeline 3 passes : `pseudonymize()` (regex + Flair NER fuzzy + fuzzy direct) |
| `src/document/yaml_template_parser.py` | Parser principal via templates YAML (PRONOTE) |
| `src/document/parser.py` | Utilitaires partagés (`extract_pdf_content`, `extract_key_value`, etc.) |
| `src/document/validation.py` | `validate_extraction()`, `check_classe_mismatch()` |
| `src/document/debug_visualizer.py` | Génère un PDF annoté pour debug visuel des zones |
| `src/document/templates/pronote_standard.yaml` | Template d'extraction PRONOTE v2.0 |

### Génération LLM

| Fichier | Responsabilité |
|---------|----------------|
| `src/generation/generator.py` | `SyntheseGenerator` (orchestration sync + async batch) |
| `src/generation/prompts.py` | Prompt `synthese_v3` (growth mindset, feedforward, SDT, biais) |
| `src/generation/prompt_builder.py` | Formatage données + construction few-shot tronqués |

### Abstraction LLM

| Fichier | Responsabilité |
|---------|----------------|
| `src/llm/manager.py` | `LLMManager` (registry, retry, rate limiting) |
| `src/llm/base.py` | `LLMClient` ABC (template method : timing, metrics, coût) |
| `src/llm/config.py` | Settings (clés API, modèles, pricing par provider) |
| `src/llm/rate_limiter.py` | `SimpleRateLimiter` (fenêtre glissante RPM par provider) |
| `src/llm/pricing.py` | `PricingCalculator` (calcul de coûts unifié) |
| `src/llm/clients/` | Implémentations OpenAI, Anthropic, Mistral |

### Privacy & Storage

| Fichier | Responsabilité |
|---------|----------------|
| `src/privacy/pseudonymizer.py` | Mapping nom ↔ eleve_id (DuckDB séparé) |
| `src/storage/repositories/` | CRUD classes, élèves, synthèses |
| `src/storage/schemas.py` | Définitions SQL + migrations idempotentes |
| `src/api/routers/exports.py` | Endpoints import/export |

## Bases de données

| Base | Contenu | Sensible |
|------|---------|----------|
| `privacy.duckdb` | Mapping eleve_id ↔ nom/prénom (scoped par classe) | **Oui** (local uniquement) |
| `chiron.duckdb` | Élèves pseudonymisés, synthèses, classes | Non (partageable) |

### Clé primaire élèves

PK composite `(eleve_id, classe_id, trimestre)` — un même élève peut avoir des données différentes par trimestre.

## RGPD

- **Extraction du nom** : locale (regex), jamais envoyée au cloud
- **Pseudonymisation** : pipeline 3 passes (regex + Flair NER fuzzy + fuzzy direct) sur les appréciations
- **Genre** : extrait et stocké localement, **non transmis** au LLM (déduit des accords grammaticaux)
- **Données transmises au LLM** : notes **catégorisées** (échelle LSU), appréciations **pseudonymisées**
- **Données non transmises** : noms, prénoms, genre, absences, retards, engagements, établissement, classe, année scolaire, noms des professeurs
- **Dépseudonymisation** : uniquement à l'export, scoped par classe
- **Cascade suppression** : supprimer un élève nettoie aussi son mapping dans `privacy.duckdb` (si plus aucun trimestre)
- **Effacement automatique** : les données de plus de 30 jours sont supprimées au lancement (Art. 5(1)(e))
- **Suppression manuelle** : bouton sur la page Export pour supprimer les données d'un trimestre après validation et export
- **Minimisation** : le texte brut PDF (`raw_text`) n'est plus persisté en base — seules les données structurées sont stockées
- **Debug visualizer** : outil de développement (`debug_visualizer.py`) qui superpose les zones détectées sur le PDF. Fonctionne uniquement en affichage temporaire, ne stocke aucune donnée en base, non concerné par la minimisation
- **Logs** : les logs de niveau INFO (défaut) ne contiennent jamais de données nominatives. Les mappings nom ↔ ELEVE_XXX ne sont loggués qu'au niveau DEBUG, réservé au développement (`LOG_LEVEL=DEBUG` dans `.env`)
- **Base légale** : mission de service public éducatif (RGPD Art. 6(1)(e)), documentée dans l'UI

## Comportement d'import

- **Écrasement** : si un élève existe déjà pour (classe_id, trimestre), les données sont écrasées
- **Synthèses** : les synthèses associées sont aussi supprimées lors de l'écrasement
- **Validation** : `check_classe_mismatch()` avertit si le niveau PDF ne correspond pas à la classe sélectionnée
- **Avertissement UI** : la page d'import affiche le nombre d'élèves existants avant import

## Convention classe_id

Format recommandé : `{niveau}{groupe}_{année}` (ex: `3A_2024-2025`)

Cela permet d'identifier facilement la classe et l'année scolaire sans modifier le schéma.

## Configuration

```bash
# .env
PDF_PARSER_TYPE=yaml_template  # yaml_template (défaut) ou pdfplumber (legacy)
DEFAULT_PROVIDER=anthropic     # openai, anthropic ou mistral
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
MISTRAL_API_KEY=...
```
