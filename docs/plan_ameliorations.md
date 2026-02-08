# Plan d'améliorations Chiron

> Date : 2026-02-08 | Branche : `feature/pdf-parser`

Principes directeurs : **DRY, KISS, YAGNI, modularité, fiabilité.**

---

## P0 — Bugs critiques (avant test utilisateur)

### ~~1. Bug "Générer manquantes"~~ — ✅ OK, fonctionne correctement

---

### ~~2. Fallback ELEVE_001 quand nom non détecté~~ — ✅ Fait

Fallback ELEVE_XXX supprimé, `ParserError` levée → HTTP 422 (unitaire) / erreur par fichier (batch). Paramètre `eleve_count` retiré.

**Reste à faire** (hors scope initial) :
- [ ] Champ de saisie manuelle du nom côté UI + paramètre `nom_override` à l'endpoint
- [ ] Table `import_log` pour traçabilité

---

## P1 — Robustesse données

### ~~3. Doublon de classes~~ — ✅ Fait

Index UNIQUE `(nom, annee_scolaire)` ajouté, vérification applicative dans `create()` → `StorageError` → HTTP 409. `get_or_create()` corrigé pour filtrer sur `(nom, annee_scolaire)`. L'UI affiche déjà l'erreur via le catch générique existant.

---

### ~~4. Doublon d'élèves (normalisation des noms)~~ — ✅ Fait

`normalize_name()` créée dans `src/core/utils.py` (NFC + strip + collapse espaces + lowercase). Colonnes `nom_normalized`/`prenom_normalized` ajoutées à `mapping_identites` avec migration automatique. Lookup et insert sur colonnes normalisées, index UNIQUE dédié. Noms originaux préservés pour dépseudonymisation.

---

### ~~5. Validation du format PDF à l'import~~ — ✅ Fait

**Fichiers** : `src/document/validation.py`, `src/api/routers/exports.py`, `app/pages/1_import.py`

`validate_extraction()` créée avec `ValidationResult` (erreurs bloquantes + warnings). Bloquant si aucune matière détectée. Warnings pour genre manquant, matières sans note ou sans appréciation. Warnings retournés dans la réponse API et affichés dans l'UI.

---

### ~~10. UX Import — Dépseudonymisation + confirmation écrasement~~ — ✅ Fait

**Fichiers** : `src/api/routers/classes.py`, `src/api/routers/exports.py`, `app/api_client.py`, `app/pages/1_import.py`

**Problèmes** :
- La "Vue de la classe" affichait les IDs pseudonymisés (`ELEVE_001`) au lieu des vrais noms
- L'import écrasait silencieusement un élève existant sans demander confirmation

**Implémentation** :
- ~~Endpoint `eleves-with-syntheses` : injection `Pseudonymizer`, ajout `prenom`/`nom` via `list_mappings()` (1 requête)~~
- ~~UI Vue de la classe : affichage `"{prenom} {nom}"` avec fallback sur `eleve_id`~~
- ~~Nouvel endpoint `POST /import/pdf/check` : extraction nom (regex, pas de NER), vérification mapping + existence → retourne `{conflicts, new, unreadable}`~~
- ~~Paramètre `force_overwrite` (défaut `True`) dans `_import_single_pdf`, `import_pdf`, `import_pdf_batch` : si `False` et élève existe → `status: "skipped"`~~
- ~~API client : `force_overwrite` sur `import_pdf`/`import_pdf_batch`, nouvelle méthode `check_pdf_duplicates`~~
- ~~UI : vérification pré-import (cache par fingerprint fichiers), bandeau warning/info avec vrais noms, checkbox cochée par défaut, résultats post-import avec compteur skipped~~

---

## P2 — Améliorations fonctionnelles

### ~~6. Génération batch (performance)~~ — ✅ Fait

**Fichiers** : `src/generation/generator.py`, `src/api/routers/syntheses.py`, `app/api_client.py`, `app/pages/2_syntheses.py`

Méthodes `async generate_with_metadata_async()` et `async generate_batch_async()` ajoutées au `SyntheseGenerator` avec `asyncio.gather()` + `asyncio.Semaphore(3)`. Endpoint `POST /syntheses/generate-batch` (async) créé. API client avec `BATCH_TIMEOUT = 600s`. UI "Générer manquantes" et "Tout régénérer" remplacées par appel batch unique avec spinner.

---

### 7. Afficher le prompt au user

**Fichiers** : `src/generation/prompts.py`, `src/api/routers/syntheses.py`

**Implémentation** :
- [ ] Ajouter un endpoint `GET /prompts/current` qui retourne :
  ```json
  {
    "version": "synthese_v2",
    "system_prompt": "...",
    "user_prompt_template": "...",
    "prompt_hash": "..."
  }
  ```
- [ ] Côté UI : ajouter un `st.expander("Voir le prompt utilisé")` sur la page synthèses, appelant cet endpoint, affichant le contenu en lecture seule

---

## P3 — Améliorations du prompt et de l'analyse

### 8. Prompt v3 — marqueurs éducatifs supplémentaires

**Fichiers** : `src/generation/prompts.py`

**Ajouts envisagés** (seulement si les bulletins PRONOTE contiennent ces données) :
- [ ] Comportement / vie scolaire (absences, retards, avis du CPE)
- [ ] Compétences transversales (autonomie, travail en groupe, oral)
- [ ] Citations exactes des appréciations (demander au LLM de citer entre guillemets)
- [ ] Progression inter-trimestre (si données T1 disponibles lors de la génération T2)

**Méthode** :
- Créer `synthese_v3` dans le dict `PROMPT_TEMPLATES` — ne pas modifier v2
- Tester sur quelques élèves avant de switcher `CURRENT_PROMPT`

---

### 9. Autres biais éducatifs

**Fichiers** : `src/generation/prompts.py:76-106`

**Biais supplémentaires à détecter** :
- [ ] **Effet Pygmalion / Golem** : attentes auto-réalisatrices ("comme d'habitude", "encore une fois")
- [ ] **Biais socio-économique** : "manque de suivi à la maison", "milieu difficile"
- [ ] **Biais de confirmation** : mêmes qualificatifs répétés trimestre après trimestre
- [ ] **Biais liés à l'origine** : attentes différenciées selon le nom de famille

**À faire** :
- [ ] Vérifier les références académiques actuelles (ligne 78 : "École d'économie de Paris, 2026")
- [ ] Ajouter des références solides : Rosenthal & Jacobson (1968), Terrail (2002), Bressoux & Pansu (2003), CNESCO (2016)
- [ ] Intégrer dans `synthese_v3` (même ticket que #8)

---

## Ordre d'exécution suggéré

```
P0 #2  Fallback ELEVE_001              ✅
  ↓
P1 #3  Doublon classes (UNIQUE)        ✅
  ↓
P1 #4  Normalisation noms élèves      ✅
  ↓
P1 #5  Validation format PDF          ✅
  ↓
P1 #10 UX Import (dépseudo + confirm) ✅
  ↓
P2 #6  Endpoint batch generation       ✅
  ↓
P2 #7  Afficher le prompt
  ↓
P3 #8  Prompt v3
  ↓
P3 #9  Biais supplémentaires
```

---

## Fichiers impactés (synthèse)

| Fichier | Tickets |
|---------|---------|
| `src/storage/schemas.py` | ~~#2~~, ~~#3~~ |
| `src/storage/connection.py` | ~~#3~~ |
| `src/storage/repositories/classe.py` | ~~#3~~ |
| `src/privacy/pseudonymizer.py` | ~~#4~~ |
| `src/api/routers/classes.py` | ~~#3~~, ~~#10~~ |
| `src/api/routers/exports.py` | ~~#2~~, #5, ~~#10~~ |
| `src/api/routers/syntheses.py` | #6, #7 |
| `src/document/anonymizer.py` | #2 |
| `src/generation/generator.py` | #6 |
| `src/generation/prompts.py` | #8, #9 |
| `app/pages/2_syntheses.py` | #6, #7 |
| `app/pages/1_import.py` | #2, #5, ~~#10~~ |
| `app/api_client.py` | #2, #6, ~~#10~~ |
| `src/core/utils.py` (nouveau) | ~~#4~~ |
