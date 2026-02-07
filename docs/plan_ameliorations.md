# Plan d'améliorations Chiron

> Date : 2026-02-06 | Branche : `feature/pdf-parser`

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

### 4. Doublon d'élèves (normalisation des noms)

**Fichiers** : `src/privacy/pseudonymizer.py:119-150`

**Problème** : Le lookup dans `_get_existing_mapping()` fait un match exact sur (nom, prenom, classe_id). Un accent ou espace en trop crée un doublon.

**Implémentation** :
- [ ] Créer une fonction `normalize_name(name: str) -> str` dans `src/core/utils.py` :
  - `strip()`, `lower()`, collapse espaces multiples, normalisation unicode (NFC)
- [ ] Appliquer cette normalisation dans `_get_existing_mapping()` et `create_eleve_id()` avant le lookup et l'insertion
- [ ] Stocker le nom normalisé en plus du nom original (colonne `nom_normalise`)

---

### 5. Validation du format PDF à l'import

**Fichiers** : `src/api/routers/exports.py:35-61`, `src/document/pdfplumber_parser.py`

**Problème** : Seuls le content-type et la taille sont vérifiés. Un PDF non-bulletin passe sans erreur.

**Implémentation** :
- [ ] Après le parsing, valider le résultat `EleveExtraction` avec des règles :
  - **Bloquant** : nom élève non détecté (cf. P0 #2)
  - **Bloquant** : aucune matière détectée (= ce n'est probablement pas un bulletin)
  - **Warning** : genre non détecté → importer quand même, afficher un avertissement
  - **Warning** : certaines matières sans note ou sans appréciation → importer, avertir
- [ ] Créer une fonction `validate_extraction(extraction: EleveExtraction) -> ValidationResult` dans `src/document/` avec liste d'erreurs et de warnings
- [ ] Retourner les warnings dans la réponse API pour affichage UI

---

## P2 — Améliorations fonctionnelles

### 6. Génération batch (performance)

**Fichiers** : `src/generation/generator.py:172-202`, `src/api/routers/syntheses.py`

**Problème** : Pas d'endpoint batch. L'UI boucle sur l'endpoint unitaire → lent, pas de parallélisme.

**Implémentation** :
- [ ] Créer `POST /syntheses/generate-batch` dans le router :
  - Paramètres : `classe_id`, `trimestre`, `eleve_ids: list[str] | None` (None = tous les manquants)
  - Réponse : liste de résultats par élève (succès/erreur)
- [ ] Dans `generator.py`, modifier `generate_batch()` pour utiliser `asyncio.gather()` avec `asyncio.Semaphore(3)` (3 appels LLM concurrents max)
- [ ] Côté UI : remplacer la boucle par un appel unique à l'endpoint batch
- [ ] Ajouter un polling ou SSE pour la progress bar (ou garder le polling HTTP simple — KISS)

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
P1 #4  Normalisation noms élèves
  ↓
P1 #5  Validation format PDF
  ↓
P2 #6  Endpoint batch generation
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
| `src/storage/schemas.py` | ~~#2~~, ~~#3~~, #4 |
| `src/storage/connection.py` | ~~#3~~ |
| `src/storage/repositories/classe.py` | ~~#3~~ |
| `src/privacy/pseudonymizer.py` | #4 |
| `src/api/routers/classes.py` | ~~#3~~ |
| `src/api/routers/exports.py` | ~~#2~~, #5 |
| `src/api/routers/syntheses.py` | #6, #7 |
| `src/document/anonymizer.py` | #2 |
| `src/generation/generator.py` | #6 |
| `src/generation/prompts.py` | #8, #9 |
| `app/pages/2_syntheses.py` | #6, #7 |
| `app/pages/1_import.py` | #2, #5 |
| `app/api_client.py` | #2, #6 |
| `src/core/utils.py` (nouveau) | #4 |
