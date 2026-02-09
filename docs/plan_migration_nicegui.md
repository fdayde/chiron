# Plan de migration Streamlit → NiceGUI

> Date : 2026-02-09 | Branche cible : `feature/nicegui-migration`

## Contexte et objectifs

**Pourquoi migrer ?**
- Packaging `.exe` natif (PyInstaller + pywebview) pour distribution aux profs non techniques
- Process unique (NiceGUI est construit sur FastAPI) → plus de double process Streamlit + FastAPI
- Mode desktop natif (`ui.run(native=True)`) via pywebview
- Les routers FastAPI existants se montent directement dans l'app NiceGUI

**Ce qui ne change PAS :**
- Tout `src/` (core, api, generation, storage, privacy, llm, document) → intact
- `app/api_client.py` → intact (les pages NiceGUI appellent l'API via HTTP comme avant, OU on passe en appels directs — voir Phase 5)
- La base DuckDB, le modèle CamemBERT, les providers LLM → inchangés

**Risque principal :**
- PyInstaller + NiceGUI native mode a des retours mitigés. Plan B : mode web avec launcher custom (ouvre le navigateur automatiquement).

---

## Inventaire du code UI actuel

| Fichier | Lignes | Complexité migration |
|---------|--------|---------------------|
| `app/main.py` | 212 | Moyenne (dashboard, custom HTML, metrics) |
| `app/pages/1_import.py` | 326 | Haute (file_uploader multi, progress bar, duplicate check) |
| `app/pages/2_syntheses.py` | 372 | Haute (@fragment, @dialog, batch, navigation prev/next) |
| `app/pages/3_Export.py` | 242 | Moyenne (download_button, text_area, preview cards) |
| `app/pages/4_Prompt.py` | 45 | Basse (lecture seule) |
| `app/components/sidebar.py` | 133 | Moyenne (global state, form, selectbox) |
| `app/components/data_helpers.py` | 112 | Basse (cache wrappers → cachetools) |
| `app/components/llm_selector.py` | 65 | Basse (2 selectbox + caption) |
| `app/components/eleve_card.py` | 103 | Moyenne (metric avec delta, containers) |
| `app/components/appreciations_view.py` | 96 | Basse (affichage, containers) |
| `app/components/synthese_editor.py` | 196 | Haute (text_area, buttons, generate/save/validate) |
| `app/config.py` | 117 | Basse (Pydantic settings, adapter le cache) |
| **Total** | **~2 020** | |

---

## Mapping des composants Streamlit → NiceGUI

| Streamlit | NiceGUI | Notes |
|-----------|---------|-------|
| `st.set_page_config()` | `@ui.page('/path')` | Routing par décorateur |
| `st.switch_page()` | `ui.navigate.to('/path')` | Navigation client-side |
| `st.sidebar` | `ui.left_drawer()` | Dans un layout partagé |
| `st.columns(3)` | `ui.row()` + `ui.column()` ou `ui.grid(columns=3)` | |
| `st.metric("Label", val, delta)` | Composant custom `MetricCard` | À créer (card + labels) |
| `st.button()` | `ui.button()` | Callback `on_click` |
| `st.selectbox()` | `ui.select()` | Binding réactif |
| `st.text_input()` | `ui.input()` | |
| `st.text_area()` | `ui.textarea()` | |
| `st.checkbox()` | `ui.checkbox()` | |
| `st.radio()` | `ui.radio()` | |
| `st.file_uploader()` | `ui.upload().props('accept=.pdf')` | Event-based |
| `st.download_button()` | `ui.button()` + `ui.download()` | |
| `st.dataframe()` | `ui.table()` ou `ui.aggrid()` | |
| `st.markdown()` | `ui.markdown()` | |
| `st.code()` | `ui.code()` | |
| `st.expander()` | `ui.expansion()` | |
| `st.container(border=True)` | `ui.card()` | |
| `st.divider()` | `ui.separator()` | |
| `st.spinner()` | `ui.spinner()` ou notification | |
| `st.progress()` | `ui.linear_progress()` | |
| `st.success/error/warning/info()` | `ui.notify()` ou `ui.badge()` | |
| `st.caption()` | `ui.label().classes('text-caption')` | Tailwind CSS |
| `@st.dialog()` | `ui.dialog()` avec `await dialog` | Awaitable |
| `@st.fragment` | `@ui.refreshable` | Recrée les éléments |
| `@st.cache_data(ttl=30)` | `@cached(TTLCache(...))` | `cachetools` |
| `@st.cache_resource` | `@cache` (functools) | Singleton |
| `st.session_state` | `app.storage.user` / `app.storage.tab` | |
| `st.rerun()` | `refreshable.refresh()` | Pas de rerun global |
| `st.stop()` | `return` (pas besoin, event-driven) | |
| `st.form()` | Pattern bouton + callbacks | Pas d'équivalent exact |
| `st.empty()` | Variable référence + `.set_text()` | Binding |

---

## Architecture cible

```
chiron/
├── src/                          # ← INCHANGÉ
│   ├── api/routers/              # Montés dans NiceGUI via app.include_router()
│   ├── core/
│   ├── document/
│   ├── generation/
│   ├── llm/
│   ├── privacy/
│   └── storage/
├── app/                          # ← RÉÉCRIT
│   ├── main.py                   # Point d'entrée unique : ui.run(native=True)
│   ├── layout.py                 # Layout partagé (header, drawer/sidebar)
│   ├── state.py                  # State management (classe_id, trimestre, etc.)
│   ├── cache.py                  # Wrappers cache (TTLCache, remplace @st.cache_data)
│   ├── components/
│   │   ├── metric_card.py        # Composant custom MetricCard (remplace st.metric)
│   │   ├── llm_selector.py       # Sélecteur provider/model
│   │   ├── eleve_card.py         # Carte élève
│   │   ├── appreciations_view.py # Vue appréciations
│   │   └── synthese_editor.py    # Éditeur de synthèse
│   └── pages/
│       ├── home.py               # @ui.page('/')
│       ├── import_page.py        # @ui.page('/import')
│       ├── syntheses.py          # @ui.page('/syntheses')
│       ├── export.py             # @ui.page('/export')
│       └── prompt.py             # @ui.page('/prompt')
└── run.py                        # Entry point : python run.py
```

### Point d'entrée (`run.py`)

```python
from nicegui import app, ui
from src.api.routers import classes, exports, syntheses

# Monter les routers FastAPI existants
app.include_router(classes.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(syntheses.router, prefix="/api")

# Importer les pages (les @ui.page sont enregistrés à l'import)
import app.pages.home
import app.pages.import_page
import app.pages.syntheses
import app.pages.export
import app.pages.prompt

ui.run(
    title="Chiron",
    native=True,          # Mode desktop via pywebview
    window_size=(1400, 900),
    reload=False,          # Désactivé en production
    storage_secret="chiron-local",  # Pour app.storage.user
)
```

### Layout partagé (`app/layout.py`)

```python
from contextlib import contextmanager
from nicegui import ui, app

@contextmanager
def page_layout(title: str):
    """Layout commun : header + drawer (sidebar) + contenu."""
    with ui.header().classes('items-center'):
        ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat color=white')
        ui.label('Chiron').classes('text-h6')
        ui.space()
        # Navigation links
        for label, path in [('Accueil', '/'), ('Import', '/import'),
                            ('Synthèses', '/syntheses'), ('Export', '/export'),
                            ('Prompt', '/prompt')]:
            ui.button(label, on_click=lambda p=path: ui.navigate.to(p)).props('flat color=white')

    with ui.left_drawer(value=True).classes('bg-blue-1') as drawer:
        render_sidebar()

    with ui.column().classes('w-full p-4'):
        ui.label(title).classes('text-h4')
        ui.separator()
        yield  # Contenu de la page
```

---

## Phases d'implémentation

### Phase 0 — Setup et infrastructure (0.5 jour)

**Objectif** : NiceGUI tourne, les routers sont montés, page blanche accessible.

- [ ] Créer branche `feature/nicegui-migration`
- [ ] Ajouter `nicegui` et `pywebview` aux dépendances (`pyproject.toml` ou `requirements.txt`)
- [ ] Créer `run.py` : monte les routers, importe les pages, lance `ui.run()`
- [ ] Créer `app/layout.py` : layout partagé avec header + drawer vide
- [ ] Créer `app/state.py` : gestion état global (`classe_id`, `trimestre`) via `app.storage.tab`
- [ ] Créer `app/cache.py` : wrappers `TTLCache` pour remplacer `@st.cache_data`
- [ ] Créer page stub `app/pages/home.py` : `@ui.page('/')` avec "Hello Chiron"
- [ ] Vérifier : `python run.py` ouvre la fenêtre native, `/api/health` répond en JSON

**Critère de validation** : L'app s'ouvre en mode desktop, l'API REST fonctionne.

---

### Phase 1 — Sidebar et navigation (0.5 jour)

**Objectif** : Navigation entre pages + sélection classe/trimestre fonctionne.

- [ ] `app/layout.py` : drawer avec sélecteur de classe (`ui.select`), sélecteur trimestre (`ui.select`), formulaire "Nouvelle classe" (`ui.expansion` + inputs)
- [ ] `app/state.py` : fonctions `get_classe_id()`, `set_classe_id()`, `get_trimestre()`, `set_trimestre()` wrappant `app.storage.tab`
- [ ] `app/cache.py` : implémenter `fetch_classes()`, `fetch_classe()`, `clear_classes_cache()` avec `TTLCache`
- [ ] Binding : changement de classe/trimestre met à jour l'état et rafraîchit la page (`ui.navigate.to(current_path)` ou `refreshable.refresh()`)
- [ ] Pages stubs pour `/import`, `/syntheses`, `/export`, `/prompt` avec layout partagé
- [ ] Header : liens de navigation, indicateur page active

**Critère de validation** : On peut naviguer entre les 5 pages, sélectionner une classe et un trimestre, créer une classe.

---

### Phase 2 — Composants réutilisables (1 jour)

**Objectif** : Tous les composants partagés sont portés.

**`app/components/metric_card.py`** :
- [ ] Composant `metric_card(label, value, delta=None, delta_color='green')` basé sur `ui.card()`
- [ ] Support du delta avec flèche et couleur (équivalent `st.metric`)
- [ ] Support `delta_color="inverse"` (vert = négatif, comme pour les absences)

**`app/components/llm_selector.py`** :
- [ ] Deux `ui.select` (provider, model) avec binding réactif
- [ ] Caption coût estimé mis à jour dynamiquement
- [ ] Retourne `(provider, model)` via state ou binding

**`app/components/eleve_card.py`** :
- [ ] `render_eleve_card(eleve)` : carte avec nom, metrics, badge statut
- [ ] `render_eleve_header(eleve)` : version détaillée pour page synthèse

**`app/components/appreciations_view.py`** :
- [ ] `render_appreciations(eleve, compact=False)` : grille matières avec notes et appréciations
- [ ] Delta note élève vs classe, containers bordés

**`app/components/synthese_editor.py`** :
- [ ] `render_synthese_editor(client, eleve, synthese, provider, model)` : textarea + boutons
- [ ] Boutons : Générer / Sauvegarder / Valider / Régénérer
- [ ] Sauvegarder activé uniquement si texte modifié (binding)
- [ ] Régénérer ouvre un `ui.dialog()` de confirmation
- [ ] Affichage insights (alertes, réussites) dans `ui.expansion()`

**Critère de validation** : Chaque composant fonctionne isolément avec des données de test.

---

### Phase 3 — Pages principales (2 jours)

#### 3a. Page Accueil (`/`) — 0.25 jour

- [ ] Metrics globaux : classes, élèves, synthèses en attente (via `metric_card`)
- [ ] Tableau récapitulatif par classe (`ui.table()`)
- [ ] Workflow visuel (3 étapes : Import → Synthèses → Export) avec `ui.card()`
- [ ] Boutons d'action rapide : `ui.navigate.to('/import')` etc.
- [ ] Notice RGPD

#### 3b. Page Import (`/import`) — 0.75 jour

- [ ] Guard : redirect si pas de classe sélectionnée
- [ ] `ui.upload(multiple=True).props('accept=.pdf')` pour upload PDF
- [ ] Preview des fichiers uploadés dans un `ui.expansion()`
- [ ] Vérification pré-import (appel `check_pdf_duplicates`) avec affichage conflits
- [ ] `ui.checkbox("Écraser les élèves existants")` si conflits détectés
- [ ] Bouton Import avec `ui.linear_progress()` + label statut
- [ ] Gestion async : itération sur les fichiers, mise à jour progress à chaque étape
- [ ] Résultats post-import : metrics (importés, écrasés, skippés, erreurs) dans `metric_card`
- [ ] Tableau récap élèves de la classe avec statut synthèse
- [ ] Bouton "Aller aux synthèses" → `ui.navigate.to('/syntheses')`

#### 3c. Page Synthèses (`/syntheses`) — 0.75 jour

- [ ] Guard : redirect si pas de classe/trimestre
- [ ] Metrics classe : total, générés, validés, en attente (`metric_card`)
- [ ] Section batch : `llm_selector` + estimation coût + bouton "Générer manquantes"
- [ ] Bouton "Tout régénérer" → `ui.dialog()` de confirmation
- [ ] Appel `generate_batch()` avec `ui.spinner()` pendant l'attente
- [ ] Filtre élèves : `ui.radio(['Tous', 'Manquantes', 'En attente', 'Validées'])` horizontal
- [ ] Navigation élève : boutons Précédent/Suivant avec compteur
- [ ] Vue split : appréciations (gauche) | éditeur synthèse (droite) — `ui.splitter()` ou `ui.grid(columns=2)`
- [ ] Nom réel de l'élève affiché (depuis `prenom_reel`/`nom_reel`)
- [ ] Barre de progression : validés / total
- [ ] `@ui.refreshable` sur la vue élève pour mise à jour sans recharger toute la page

#### 3d. Page Export (`/export`) — 0.25 jour

- [ ] Guard : redirect si pas de classe
- [ ] Recap metrics : élèves, générés, validés, en attente
- [ ] Coût tokens (si dispo via `get_classe_stats()`)
- [ ] Warnings si synthèses manquantes ou non validées
- [ ] Preview : filtre par statut (`ui.select`), cards avec texte tronqué
- [ ] Bouton CSV : `ui.button("Télécharger CSV")` → `ui.download(bytes, filename)`
- [ ] Zone copier-coller : `ui.textarea(readonly=True)` avec toutes les synthèses validées

#### 3e. Page Prompt (`/prompt`) — 0.1 jour

- [ ] 3 metrics : template name, version, hash
- [ ] `ui.code()` pour system prompt et user template
- [ ] Page lecture seule, la plus simple

**Critère de validation** : Parcours complet Import → Synthèses → Export fonctionne.

---

### Phase 4 — Polissage et tests (0.5 jour)

- [ ] Thème / couleurs cohérents (Tailwind classes via `.classes()`)
- [ ] Responsive : vérifier que le layout fonctionne sur différentes tailles de fenêtre
- [ ] Gestion d'erreurs : `ui.notify(type='negative')` pour les erreurs API
- [ ] Messages de chargement cohérents (spinners, progress bars)
- [ ] Favicon et titre de fenêtre
- [ ] Tester le parcours complet avec des vrais PDFs
- [ ] Comparer visuellement avec l'UI Streamlit actuelle (pas de régression fonctionnelle)

**Critère de validation** : Parité fonctionnelle avec Streamlit atteinte.

---

### Phase 5 — Optimisation : appels directs (optionnel, 0.5 jour)

Actuellement les pages UI appellent l'API via HTTP (`api_client.py`). Comme tout tourne dans le même process, on **peut** appeler les services directement (sans réseau) :

```python
# Avant (via HTTP)
client = ChironAPIClient()
eleves = client.get_eleves(classe_id, trimestre)

# Après (appel direct)
from src.storage.repositories.eleve import EleveRepository
repo = EleveRepository(connection)
eleves = repo.list_by_classe(classe_id, trimestre)
```

**Avantages** : Latence réduite, pas de sérialisation JSON, plus simple.
**Inconvénients** : Couplage plus fort UI ↔ backend, perte de la séparation API.

**Recommandation** : Garder `api_client.py` pour la V1. Les routers FastAPI restent montés et accessibles. Optimiser en appels directs uniquement si la latence HTTP locale pose problème (peu probable).

---

### Phase 6 — Packaging `.exe` (1 jour)

- [ ] Créer `build.py` ou `chiron.spec` pour PyInstaller
- [ ] Tester `pyinstaller --onedir run.py` avec NiceGUI
- [ ] Inclure les assets statiques si nécessaire
- [ ] Tester le mode `native=True` dans le `.exe`
- [ ] **Plan B** si native mode échoue : `ui.run(native=False)` + script qui lance le serveur et ouvre le navigateur par défaut
- [ ] Tester sur une machine Windows vierge (sans Python installé)
- [ ] Créer un installeur Inno Setup si besoin (optionnel)
- [ ] Documenter la procédure d'installation

**Points d'attention :**
- torch/transformers (~2 GB) sera inclus → l'exe sera lourd, c'est attendu
- Variables d'environnement (clés API LLM) → fichier `.env` à côté de l'exe, ou UI de configuration
- Première exécution : le modèle CamemBERT peut prendre ~60s à charger

**Critère de validation** : Double-clic sur l'exe → l'app s'ouvre, on peut importer un PDF et générer une synthèse.

---

## Estimation effort total

| Phase | Effort | Dépend de |
|-------|--------|-----------|
| 0 — Setup | 0.5 j | — |
| 1 — Sidebar + nav | 0.5 j | Phase 0 |
| 2 — Composants | 1 j | Phase 0 |
| 3 — Pages | 2 j | Phases 1 + 2 |
| 4 — Polissage | 0.5 j | Phase 3 |
| 5 — Appels directs | 0.5 j (optionnel) | Phase 3 |
| 6 — Packaging .exe | 1 j | Phase 4 |
| **Total** | **5–6 jours** | |

Les phases 1 et 2 sont parallélisables (pas de dépendance entre elles).

---

## Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| PyInstaller + NiceGUI native mode instable | Bloquant pour .exe | Plan B : mode web + launcher (ouvre Chrome/Edge) |
| Taille de l'exe (~2-3 GB avec torch) | UX distribution | ONNX Runtime (~200 MB) pour remplacer torch (hors scope migration) |
| Pas d'équivalent exact `@st.fragment` | Recharges inutiles | `@ui.refreshable` couvre le besoin |
| Pas de `st.metric` natif | Effort supplémentaire | Composant custom simple (~20 lignes) |
| `ui.upload` moins intuitif que `st.file_uploader` | UX dégradée | Props Quasar pour customiser l'apparence |
| Perte du cache Streamlit inter-pages | Données rechargées | `TTLCache` de `cachetools` + state global |

---

## Décisions à prendre avant de commencer

1. **Garder `api_client.py` ou appels directs ?** → Recommandation : garder le client HTTP pour la V1
2. **Mode native ou mode web pour le .exe ?** → Tester native d'abord, fallback web
3. **Garder la branche `feature/pdf-parser` ou créer une nouvelle branche ?** → Nouvelle branche `feature/nicegui-migration` depuis `main`
4. **Migrer les tickets #8/#9 avant ou après ?** → Après (la migration ne touche pas `src/generation/prompts.py`)

---

## Commandes utiles

```bash
# Installation
pip install nicegui pywebview

# Dev (hot reload)
python run.py  # native=True par défaut

# Dev mode web (pour debug)
CHIRON_NATIVE=0 python run.py

# Build exe
pip install pyinstaller
pyinstaller chiron.spec

# Test exe
dist/chiron/chiron.exe
```
