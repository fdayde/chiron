# Adapter Chiron à un autre format de bulletin

Le parsing est conçu pour un format de bulletin **PRONOTE** particulier (PDF tabulaire, 4 colonnes : matière, moyennes, programme, appréciations). Pour l'adapter à un autre logiciel scolaire (EcoleDirecte, Siecle, etc.) ou un format PRONOTE différent, voici les approches possibles.

> **Bulletin exemple** : un PDF de référence au format PRONOTE fictif est disponible dans [`data/demo/bulletin_fictif.pdf`](../data/demo/bulletin_fictif.pdf).

## Approche recommandée : template YAML

Depuis la v2.0, le parser principal utilise un **template YAML** qui décrit les règles d'extraction sans modifier le code Python. C'est la méthode recommandée.

### Créer un nouveau template

1. Copier le template existant :
```bash
cp src/document/templates/pronote_standard.yaml src/document/templates/mon_format.yaml
```

2. Adapter les règles d'extraction dans le nouveau fichier YAML.

### Structure du template

```yaml
template:
  name: "mon_format"
  version: "1.0"

# Champs extraits du texte brut du PDF
fields:
  genre:
    method: "key_value"      # Cherche "Clé : Valeur" dans le texte
    key: "Genre"             # Regex du label à chercher
    normalize:               # Mapping optionnel des valeurs
      fille: "Fille"
      f: "Fille"

  absences:
    method: "key_value"
    key: "Absences?"         # Regex (ici : "Absence" ou "Absences")
    extract: "number"        # Extraire le premier nombre trouvé
    cast: "int"

  moyenne_generale:
    method: "key_value"
    key: "Moyenne\\s+g[ée]n[ée]rale"
    extract: "number"

  trimestre:
    method: "regex"          # Extraction par regex avec groupe de capture
    pattern: "Trimestre\\s*(\\d)"
    cast: "int"

  engagements:
    method: "key_value"
    key: "Engagements?"
    extract: "engagements"   # Parsing spécifique (liste séparée par virgules)

# Règles d'extraction des tableaux de matières
tables:
  min_rows: 2
  columns:
    matiere_and_prof: 0      # Index de colonne : matière (+ prof si prof_in_matiere_col)
    notes: 1                 # Index de colonne : moyennes
    programme: 2             # Index de colonne : programme (optionnel)
    appreciation: 3          # Index de colonne : appréciation enseignant
  prof_in_matiere_col: true  # Le nom du prof est sous le nom de la matière
  footer_marker: "Absences"  # Texte marquant le début du footer de table
  min_appreciation_length: 5
```

### Méthodes d'extraction disponibles

| Méthode | Description | Paramètres |
|---------|-------------|------------|
| `key_value` | Cherche `"Clé : Valeur"` ou `"Clé\n: Valeur"` | `key` (regex), `extract` (number/contains/engagements), `normalize` (mapping) |
| `regex` | Extraction par groupe de capture | `pattern` (regex avec groupe), `cast` (int/float) |

### Activer le template

Pour l'instant, le template est en dur dans `YamlTemplateParser.__init__()` (`pronote_standard.yaml`). Pour utiliser un autre template, modifier cette référence ou ajouter une variable d'environnement.

## Approche alternative : parser Python custom

Pour des formats très différents (structure non tabulaire, PDF scannés, etc.), vous pouvez créer un parser Python dédié.

### 1. Extraction du nom de l'élève

**Fichier** : `src/document/anonymizer.py` — fonction `extract_eleve_name()`

Le nom est extrait via deux stratégies regex :
- **Format test** : `"Élève : NOM Prénom"` → regex `r"[ÉE]l[èe]ve\s*:\s*([^\n]+)"`
- **Format PRONOTE réel** : `"NOM Prénom\nNé(e) le..."` → regex dédiée

Adaptez ces regex au label de votre format (ex: `"Nom :"`, `"Apprenant :"`, etc.).

### 2. Créer un nouveau parser

Implémenter le protocole `PDFParser` défini dans `src/document/__init__.py` :

```python
class PDFParser(Protocol):
    def parse(
        self,
        pdf_data: bytes | str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> EleveExtraction: ...
```

Utiliser les utilitaires partagés de `src/document/parser.py` :
- `extract_pdf_content(pdf_path)` → `PDFContent` (text + tables)
- `extract_key_value(text, regex)` → valeur extraite
- `extract_number(text)` → premier nombre trouvé
- `parse_engagements(text)` → liste d'engagements

### 3. Enregistrer le parser

Ajouter le nouveau parser dans `src/document/__init__.py` :
- Ajouter le cas dans la factory `get_parser()`

### 4. Modèle de données

**Fichier** : `src/core/models.py` — classes `MatiereExtraction` et `EleveExtraction`

Le modèle de données attendu en sortie du parser. Si votre format contient des champs supplémentaires (compétences, notes par type d'épreuve, etc.), ajoutez-les ici. Le reste du pipeline (génération, UI) s'adaptera automatiquement si les champs de base sont présents.

### 5. Validation

**Fichier** : `src/document/validation.py` — fonction `validate_extraction()`

Définit les règles de validation post-extraction (erreurs bloquantes et avertissements). Ajustez selon les champs disponibles dans votre format.

## En résumé

```
Adapter à un nouveau format :

  Option A — Template YAML (recommandé) :
    templates/mon_format.yaml  → règles d'extraction déclaratives
    anonymizer.py              → regex du nom de l'élève (si différent)

  Option B — Parser Python custom :
    mon_parser.py              → implémenter PDFParser Protocol
    anonymizer.py              → regex du nom de l'élève
    __init__.py                → enregistrer dans get_parser()
    models.py                  → champs supplémentaires (optionnel)
    validation.py              → règles de validation (optionnel)
```
