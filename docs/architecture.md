# Architecture Chiron

## Flux d'import PDF

```
PDF
 │
 ▼
┌─────────────────────────────────────┐
│ 1. extract_eleve_name()             │  pdfplumber (local, regex)
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
│ 3. parser.parse()                   │  pdfplumber / yaml_template (local)
│    → EleveExtraction                │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 4. _pseudonymize_extraction()       │  Regex + NER safety net (CamemBERT)
│    → textes avec noms remplacés     │  sur les appréciations
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 5. eleve_repo.create()              │  Stocke dans chiron.duckdb
└─────────────────────────────────────┘
```

## Flux de génération

```
EleveExtraction
 │
 ▼
┌─────────────────────────────────────┐
│ 1. prompt_builder.format_eleve_data │  Formate les données élève
│    → texte structuré                │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 2. get_fewshot_examples()           │  Charge 0-3 exemples validés
│    + build_fewshot_examples()       │  (is_fewshot_example = TRUE)
│    → exemples tronqués             │  Appréciations: 1ère phrase
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
synthese_repo.get_validated() → pseudonymizer.depseudonymize_text() → CSV (noms réels)
```

## Composants

| Fichier | Responsabilité |
|---------|----------------|
| `src/document/anonymizer.py` | `extract_eleve_name()`, `ner_check_student_names()` |
| `src/document/pdfplumber_parser.py` | Parser local |
| `src/document/yaml_template_parser.py` | Parser configurable via templates YAML |
| `src/privacy/pseudonymizer.py` | Mapping nom ↔ eleve_id |
| `src/api/routers/exports.py` | Endpoints import/export |
| `src/generation/generator.py` | `SyntheseGenerator` (orchestration) |
| `src/generation/prompts.py` | Prompt synthese_v3 (growth mindset, feedforward, SDT, biais) |
| `src/generation/prompt_builder.py` | Formatage données + construction few-shot tronqués |
| `src/llm/manager.py` | `LLMManager` (registry, retry, rate limiting) |
| `src/llm/base.py` | `LLMClient` ABC (template method : timing, metrics, coût) |
| `src/llm/clients/` | Implémentations OpenAI, Anthropic, Mistral |
| `src/llm/pricing.py` | `PricingCalculator` (calcul de coûts unifié) |
| `src/llm/config.py` | Settings (clés API, modèles, pricing par provider) |

## Bases de données

| Base | Contenu | Sensible |
|------|---------|----------|
| `privacy.duckdb` | Mapping eleve_id ↔ nom/prénom | **Oui** (local uniquement) |
| `chiron.duckdb` | Élèves anonymisés, synthèses | Non |

## RGPD

- **Extraction du nom** : locale (jamais envoyée au cloud)
- **Pseudonymisation** : regex sur tous les textes + NER safety net sur les appréciations
- **Dépseudonymisation** : uniquement à l'export, scoped par classe

## Comportement d'import

- **Écrasement** : si un élève existe déjà pour (classe_id, trimestre), les données sont écrasées
- **Synthèses** : les synthèses associées sont aussi supprimées lors de l'écrasement
- **Avertissement UI** : la page d'import affiche le nombre d'élèves existants avant import

## Convention classe_id

Format recommandé : `{niveau}{groupe}_{année}` (ex: `3A_2024-2025`)

Cela permet d'identifier facilement la classe et l'année scolaire sans modifier le schéma.

## Configuration

```bash
# .env
PDF_PARSER_TYPE=yaml_template  # ou pdfplumber
OPENAI_API_KEY=...
```
