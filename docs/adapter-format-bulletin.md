# Adapter Chiron à un autre format de bulletin

Le parsing est conçu pour un format de bulletin **PRONOTE** particulier (PDF tabulaire, 4 colonnes : matière, moyennes, programme, appréciations). Pour l'adapter à un autre logiciel scolaire (EcoleDirecte, Siecle, etc.) ou un format PRONOTE différent, voici les fichiers à modifier.

> **Bulletin exemple** : un PDF de référence au format PRONOTE fictif est disponible dans [`data/demo/bulletin_fictif.pdf`](../data/demo/bulletin_fictif.pdf).

## 1. Extraction du nom de l'élève

**Fichier** : `src/document/anonymizer.py` — fonction `extract_eleve_name()`

Le nom est extrait via une regex qui cherche le label `"Élève :"` :
```python
r"[ÉE]l[èe]ve\s*:\s*([^\n]+)"
```
→ Adaptez cette regex au label de votre format (ex: `"Nom :"`, `"Apprenant :"`, etc.).

## 2. Extraction des champs clé-valeur

**Fichier** : `src/document/pdfplumber_parser.py` — fonction `parse()` (ligne ~186)

Les champs suivants sont extraits par recherche de mots-clés dans le texte brut du PDF :

| Champ | Regex actuelle | Exemple PRONOTE |
|-------|---------------|-----------------|
| Genre | `"Genre"` | `Genre : Fille` |
| Absences | `r"Absences?"` | `Absences : 3 dont 2 justifiées` |
| Engagements | `r"Engagements?"` | `Engagements : Délégué de classe` |
| Moyenne générale | `r"Moyenne\s+g[ée]n[ée]rale"` | `Moyenne générale : 14.5` |

→ Modifiez les regex dans `parse()` pour correspondre aux labels de votre format. La fonction utilitaire `extract_key_value(text, regex)` gère deux formats : `"Clé : Valeur"` (même ligne) et `"Clé\n: Valeur"` (saut de ligne).

## 3. Extraction des matières (tables)

**Fichier** : `src/document/pdfplumber_parser.py` — fonction `parse_raw_tables()` (ligne ~83)

Le parser s'attend à des tables PDF avec :
- **Colonne 1** : nom de la matière
- **Colonne 2** : moyennes au format `"15.5 / 10.8"` (élève / classe)
- **Dernière colonne** : appréciation de l'enseignant

→ Si votre format a une structure de colonnes différente, adaptez `parse_raw_tables()` et la regex de parsing des notes :
```python
r"(\d+[,.]?\d*)\s*[/|]\s*(\d+[,.]?\d*)"
```

## 4. Modèle de données

**Fichier** : `src/core/models.py` — classes `MatiereExtraction` et `EleveExtraction`

Le modèle de données attendu en sortie du parser. Si votre format contient des champs supplémentaires (compétences, notes par type d'épreuve, etc.), ajoutez-les ici. Le reste du pipeline (génération, UI) s'adaptera automatiquement si les champs de base sont présents.

## 5. Validation

**Fichier** : `src/document/validation.py` — fonction `validate_extraction()`

Définit les règles de validation post-extraction (erreurs bloquantes et avertissements). Ajustez selon les champs disponibles dans votre format.

## En résumé

```
Modifier pour un nouveau format :
  anonymizer.py        → regex du nom de l'élève
  pdfplumber_parser.py → regex des champs + structure des tables
  models.py            → champs supplémentaires (optionnel)
  validation.py        → règles de validation (optionnel)
```
