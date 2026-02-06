# Plan de corrections - Chiron

> Revue effectuee le 2026-02-06. Cocher les cases au fur et a mesure.

---

## P0 - Bugs critiques (avant test utilisateur)

### BUG-01: `annee_scolaire` hardcodee "2024-2025"

- **Impact** : Toutes les classes creees auront la mauvaise annee scolaire
- **Fichiers** :
  - `src/storage/repositories/classe.py:19` - dataclass `Classe` default
  - `src/storage/schemas.py:30` - SQL `DEFAULT '2024-2025'`
  - `src/api/routers/classes.py:19` - `ClasseCreate` model default
- **Correction** : Calculer dynamiquement l'annee scolaire (si mois >= 9 alors YYYY/YYYY+1, sinon YYYY-1/YYYY). La sidebar a deja `_get_current_school_year()` dans `app/components/sidebar.py` - reutiliser cette logique cote backend.
- [ ] Corrige
- [ ] Teste

---

### BUG-02: `_execute_write` retourne `None` -> `delete_for_eleve` toujours 0

- **Impact** : La suppression de syntheses fonctionne mais le compteur retourne est toujours 0, les logs sont faux
- **Fichiers** :
  - `src/storage/repositories/base.py:173-184` - `_execute_write` n'a pas de `return`
  - `src/storage/repositories/synthese.py:220-224` - `delete_for_eleve` tente `result.rowcount`
- **Correction** : Faire retourner le nombre de lignes affectees par `_execute_write`. DuckDB ne supporte pas `rowcount` directement, utiliser `conn.execute(...).fetchone()` avec un `SELECT changes()` ou retourner le resultat de `execute()`.
- [ ] Corrige
- [ ] Teste

---

### BUG-03: Aucune validation de taille/type sur l'upload PDF

- **Impact** : Un fichier volumineux peut saturer la memoire du serveur
- **Fichiers** :
  - `src/api/routers/exports.py:170-225` - `import_pdf`
  - `src/api/routers/exports.py:228-303` - `import_pdf_batch`
- **Correction** :
  - Ajouter une limite de taille (ex: 20 Mo par fichier)
  - Verifier le content-type (`application/pdf`)
  - Limiter le nombre de fichiers en batch (ex: 50 max)
- [ ] Corrige
- [ ] Teste

---

### BUG-04: Cle API vide -> erreur cryptique au lieu de message clair

- **Impact** : L'utilisateur ne comprend pas pourquoi la generation echoue
- **Fichiers** :
  - `src/llm/config.py:26-29` - cles API defaut `""`
  - `src/llm/clients/openai.py` / `anthropic.py` / `mistral.py` - constructeurs
- **Correction** : Valider au moment de `LLMManager.get_client()` que la cle API du provider n'est pas vide. Lever une `ConfigurationError` avec un message clair : "Cle API {provider} non configuree. Ajoutez {VAR_NAME} dans votre fichier .env"
- [ ] Corrige
- [ ] Teste

---

### BUG-05: Incoherence temperature par defaut (0.7 vs 0.0)

- **Impact** : Resultats LLM non-deterministes sans raison apparente pour l'utilisateur
- **Fichiers** :
  - `src/llm/config.py:98` - `default_temperature: float = 0.0`
  - `app/api_client.py:146` - `temperature: float = 0.7`
- **Correction** : Aligner `api_client.py` sur la valeur du backend (0.0), ou mieux, ne pas envoyer de temperature par defaut et laisser le backend decider.
- [ ] Corrige
- [ ] Teste

---

### BUG-06: API sans authentification + bind 0.0.0.0

- **Impact** : N'importe qui sur le reseau peut acceder aux endpoints (supprimer classes, eleves...)
- **Fichiers** :
  - `src/api/main.py` - pas de middleware auth
  - `src/api/config.py:9` - `host: str = "0.0.0.0"`
  - `.env.example:31` - `API_KEY` definie mais jamais utilisee
- **Correction** : Option A (rapide) : Changer le host par defaut a `127.0.0.1`. Option B (robuste) : Implementer le middleware API key en utilisant la variable `API_KEY` deja prevue dans `.env.example`.
- [ ] Corrige
- [ ] Teste

---

## P1 - Bugs importants (corriger rapidement)

### BUG-07: `json.loads` sans try/except dans `SyntheseRepository._row_to_entity`

- **Impact** : Du JSON corrompu en base crash toute la page de syntheses
- **Fichiers** :
  - `src/storage/repositories/synthese.py:34-35`
- **Correction** : Entourer les `json.loads` d'un try/except, retourner une liste vide en cas d'erreur et logger un warning.
- [ ] Corrige
- [ ] Teste

---

### BUG-08: `except Exception: pass` silencieux dans la generation batch

- **Impact** : L'utilisateur voit "0 erreurs" alors que des generations ont echoue
- **Fichiers** :
  - `app/pages/2_syntheses.py:118-119` - generation batch, erreur comptee mais pas loggee
  - `app/pages/2_syntheses.py:161-162` - regeneration, erreur completement avalee
  - `app/pages/3_Export.py:85-86` - stats LLM silencieusement ignorees
- **Correction** : Logger l'exception (`logger.error`) et afficher un `st.warning` avec le nom de l'eleve et un message d'erreur comprehensible.
- [ ] Corrige
- [ ] Teste

---

### BUG-09: Retry LLM ne gere que `ConnectionError`/`TimeoutError`

- **Impact** : Les erreurs 429 (rate limit) causent un echec immediat au lieu d'un retry
- **Fichiers** :
  - `src/llm/manager.py:89-93` - decorateur `@retry`
- **Correction** : Ajouter `openai.RateLimitError`, `anthropic.RateLimitError`, `httpx.ReadTimeout` a la liste des exceptions retryables.
- [ ] Corrige
- [ ] Teste

---

### BUG-10: `@app.on_event("startup")` deprecie dans FastAPI

- **Impact** : Avertissements de deprecation, sera retire dans une future version
- **Fichiers** :
  - `src/api/main.py:37-41`
- **Correction** : Migrer vers le pattern `lifespan` context manager de FastAPI.
- [ ] Corrige
- [ ] Teste

---

### BUG-11: PyMuPDF `doc` jamais ferme dans l'anonymizer

- **Impact** : Fichier PDF potentiellement verrouille sur Windows
- **Fichiers** :
  - `src/document/anonymizer.py:200-218`
- **Correction** : Utiliser `doc` comme context manager (`with fitz.open(pdf_path) as doc:`), ou appeler `doc.close()` dans un `finally`.
- [ ] Corrige
- [ ] Teste

---

### BUG-12: `httpx.Client` jamais ferme dans le client API

- **Impact** : Fuite de ressources (sockets) sur Windows
- **Fichiers** :
  - `app/api_client.py:27`
- **Correction** : Ajouter une methode `close()` ou un `__del__` qui appelle `self._client.close()`.
- [ ] Corrige
- [ ] Teste

---

## P2 - Robustesse (ameliorations recommandees)

### ROB-01: UUID tronque a 8 caracteres pour les IDs

- **Impact** : Risque de collision (50% a ~77k IDs par birthday paradox)
- **Fichiers** :
  - `src/storage/repositories/classe.py:53`
  - `src/storage/repositories/synthese.py:75`
- **Correction** : Utiliser au moins 12 caracteres, ou un UUID complet.
- [ ] Corrige

---

### ROB-02: Erreurs HTTP qui leakent des details internes

- **Impact** : L'utilisateur voit des stack traces, chemins de fichiers dans les erreurs
- **Fichiers** :
  - `src/api/routers/exports.py:221` - `detail=str(e)`
  - Pattern similaire dans d'autres routers
- **Correction** : Logger l'erreur complete cote serveur, retourner un message generique a l'utilisateur.
- [ ] Corrige

---

### ROB-03: NER pipeline charge sans thread safety

- **Impact** : Chargement double du modele en cas de requetes concurrentes
- **Fichiers** :
  - `src/document/anonymizer.py:32-47` - global `_ner_pipeline`
- **Correction** : Ajouter un `threading.Lock` autour du chargement.
- [ ] Corrige

---

### ROB-04: Mistral OCR retourne des donnees non structurees

- **Impact** : Les eleves importes via Mistral OCR n'ont ni matieres, ni notes, ni absences
- **Fichiers** :
  - `src/document/mistral_parser.py:90-97`
- **Correction** : Warning ajoute dans l'UI (page import).
- [x] Warning UI ajoute
- **Piste future** : Reutiliser les fonctions d'extraction du pdfplumber parser (`extract_key_value`, `extract_number`, `parse_engagements`) sur le `raw_text` markdown de Mistral OCR, et parser les tables markdown pour extraire les matieres. A tester avec des vrais PDFs via Mistral OCR d'abord.

---

## P3 - Refactoring DRY / KISS (pendant la phase UX)

### REF-01: Clients LLM - code duplique (timing, metrics, error handling)

- **Fichiers** : `src/llm/clients/openai.py`, `anthropic.py`, `mistral.py`
- **Action** : Extraire un template method dans `base.py` pour le boilerplate commun (~130 lignes x3)
- [ ] Fait

---

### REF-02: Prompts v1/v2 - 50+ lignes de copier-coller

- **Fichier** : `src/generation/prompts.py:26-210`
- **Action** : Composer les prompts depuis des blocs partages (etapes 1-5 communes, etape 6 ajoutee pour v2)
- [ ] Fait

---

### REF-03: `generate_batch` et `generate_batch_with_metadata` quasi-identiques

- **Fichier** : `src/generation/generator.py:153-215`
- **Action** : `generate_batch` delegue a `generate_batch_with_metadata` et extrait `.synthese`
- [ ] Fait

---

### REF-04: Calcul de cout duplique entre `app/config.py` et `src/llm/pricing.py`

- **Action** : Supprimer la reimplementation dans `app/config.py`, utiliser `PricingCalculator`
- [ ] Fait

---

### REF-05: `sys.path` manipulation dans chaque page Streamlit

- **Fichiers** : `app/pages/1_import.py`, `2_syntheses.py`, `3_Export.py`
- **Action** : Installer le package en mode dev (`pip install -e .`) et supprimer les manipulations `sys.path`
- [ ] Fait

---

### REF-06: Pattern "get or 404" repete dans les routers

- **Fichiers** : `src/api/routers/classes.py`, `eleves.py`, `syntheses.py`
- **Action** : Creer un helper `get_or_404(repo, entity_id, entity_name)` ou une dependance FastAPI
- [ ] Fait

---

## P4 - Code mort YAGNI (nettoyage rapide)

### YAGNI-01: `Repository[T]` ABC inutilise

- **Fichier** : `src/storage/repositories/base.py:21-91`
- **Action** : Supprimer, garder `DuckDBRepository` comme base directe
- [ ] Fait

---

### YAGNI-02: `calculate_batch_cost()` jamais appele

- **Fichier** : `src/llm/pricing.py:91-149`
- **Action** : Supprimer
- [ ] Fait

---

### YAGNI-03: Table `exemples_fewshot` sans repository ni usage

- **Fichier** : `src/storage/schemas.py:110-118`
- **Action** : Supprimer la creation de la table (ou la garder si c'est dans la roadmap proche)
- [ ] Fait

---

### YAGNI-04: `Pseudonymizer.pseudonymize()` jamais appele

- **Fichier** : `src/privacy/pseudonymizer.py:106-148`
- **Action** : Supprimer
- [ ] Fait

---

### YAGNI-05: `ValidationError`, `ConfigurationError` jamais levees

- **Fichier** : `src/core/exceptions.py:80-101`
- **Action** : Garder `ConfigurationError` (utile pour BUG-04), supprimer `ValidationError`
- [ ] Fait

---

### YAGNI-06: `BULLETIN_LAYOUT` dict inutilise

- **Fichier** : `src/document/templates.py:102-114`
- **Action** : Supprimer
- [ ] Fait

---

### YAGNI-07: `render_classe_selector()` legacy wrapper vide

- **Fichier** : `app/components/sidebar.py:141-146`
- **Action** : Supprimer
- [ ] Fait

---

### YAGNI-08: `API_KEY` et `MAPPING_ENCRYPTION_KEY` dans `.env.example` non utilises

- **Fichier** : `.env.example`
- **Action** : Retirer `MAPPING_ENCRYPTION_KEY`. Garder `API_KEY` si BUG-06 option B est implementee.
- [ ] Fait

---

## P5 - Documentation

### DOC-01: README - version Python incorrecte (dit 3.11+, devrait etre 3.13+)

- [ ] Corrige

### DOC-02: README - URL git clone placeholder `[user]`

- [ ] Corrige

### DOC-03: README - noms de modeles obsoletes (GPT-4o-mini -> GPT-5-mini)

- [ ] Corrige

### DOC-04: README - table de couts obsolete

- [ ] Corrige

### DOC-05: README - diagramme de structure incomplet

- [ ] Corrige

### DOC-06: README - section configuration incomplete (6 vars sur 14)

- [ ] Corrige

### DOC-07: README - ajouter mention de Swagger UI a `/docs`

- [ ] Corrige

### DOC-08: `docs/architecture.md` - composants LLM manquants

- [ ] Corrige

### DOC-09: `src/llm/README.md` - pipeline consensus decrit mais non implemente

- [ ] Corrige

### DOC-10: Etablir une convention de langue pour les docstrings (FR ou EN)

- [ ] Decide et applique
