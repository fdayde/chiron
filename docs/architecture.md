# Architecture Chiron

## Flux d'import PDF

```
PDF
 │
 ▼
┌─────────────────────────────────────┐
│ 1. extract_eleve_name()             │  pdfplumber (local)
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
│ 3. anonymize_pdf()                  │  NER (CamemBERT) + PyMuPDF
│    → PDF avec noms remplacés        │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 4. parser.parse()                   │  pdfplumber (local)
│    OU Mistral OCR (cloud)           │  ou Mistral OCR (cloud, RGPD OK)
│    → EleveExtraction                │
└─────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ 5. eleve_repo.create()              │  Stocke dans chiron.duckdb
└─────────────────────────────────────┘
```

## Flux de génération

```
EleveExtraction → PromptBuilder → LLM (OpenAI/Anthropic/Mistral) → Synthese → chiron.duckdb
```

## Flux d'export

```
synthese_repo.get_validated() → pseudonymizer.depseudonymize_text() → CSV (noms réels)
```

## Composants

| Fichier | Responsabilité |
|---------|----------------|
| `src/document/anonymizer.py` | `extract_eleve_name()`, `anonymize_pdf()` |
| `src/document/pdfplumber_parser.py` | Parser local |
| `src/document/mistral_parser.py` | Parser cloud (Mistral OCR) |
| `src/privacy/pseudonymizer.py` | Mapping nom ↔ eleve_id |
| `src/api/routers/exports.py` | Endpoints import/export |
| `src/generation/generator.py` | Appel LLM |
| `src/generation/prompts.py` | Templates de prompts |

## Bases de données

| Base | Contenu | Sensible |
|------|---------|----------|
| `privacy.duckdb` | Mapping eleve_id ↔ nom/prénom | **Oui** (local uniquement) |
| `chiron.duckdb` | Élèves anonymisés, synthèses | Non |

## RGPD

- **Extraction du nom** : locale (jamais envoyée au cloud)
- **Anonymisation** : AVANT tout envoi cloud
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
PDF_PARSER_TYPE=pdfplumber  # ou mistral_ocr
MISTRAL_OCR_API_KEY=...     # si mistral_ocr
OPENAI_API_KEY=...
```
