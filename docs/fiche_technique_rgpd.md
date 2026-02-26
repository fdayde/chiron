# Fiche technique RGPD — Chiron

> **Ce document n'est ni une AIPD ni une notice d'information aux familles.**
>
> Il fournit les éléments techniques et factuels dont le responsable de traitement (RT) et le DPO académique ont besoin pour produire leurs propres documents réglementaires.

---

## Obligations du responsable de traitement

Avant toute mise en service de Chiron, le chef d'établissement (2nd degré) ou le DASEN (1er degré), en tant que responsable de traitement, doit :

1. **Réaliser ou faire réaliser une AIPD** (Art. 35 RGPD) — Le traitement réunit au moins trois critères déclencheurs identifiés par le G29 (lignes directrices WP 248) et repris par la CNIL : personnes vulnérables (élèves mineurs), usage innovant (IA générative), évaluation de personnes (synthèses du parcours scolaire).

2. **Informer les familles** (Art. 13 RGPD) — Une note d'information doit être diffusée avant la première utilisation (ENT, courrier joint au bulletin, réunion de rentrée). Conformément au cadre d'usage de l'IA en éducation du Ministère (juin 2025), l'utilisation de l'IA doit faire l'objet d'une communication explicite.

3. **Inscrire le traitement au registre des activités** (Art. 30 RGPD).

4. **Associer le DPO académique** à la démarche.

### Références réglementaires

- Règlement (UE) 2016/679 (RGPD), en particulier les articles 35 et 36
- Règlement (UE) 2024/1689 sur l'intelligence artificielle (RIA)
- Loi n° 78-17 du 6 janvier 1978 modifiée (Informatique et Libertés)
- Cadre d'usage de l'IA en éducation, Ministère de l'Éducation nationale, juin 2025
- FAQ CNIL « Enseignant : comment utiliser un système d'IA » et « Responsable de traitement », juin 2025

---

## 1. Description du traitement

### 1.1 Finalité

Aider les enseignants à préparer les conseils de classe en générant des **projets de synthèses trimestrielles** à partir des bulletins scolaires (PDF PRONOTE).

Les synthèses sont des **propositions** soumises à la relecture, la modification et la validation obligatoire de l'enseignant avant tout export. L'outil ne se substitue pas au jugement professionnel de l'enseignant.

### 1.2 Ce que Chiron ne fait pas

- Aucune catégorisation automatisée des élèves (pas de scoring, pas de profilage, pas d'étiquetage)
- Aucune décision automatisée au sens de l'Art. 22 RGPD
- Les sorties sont exclusivement des textes narratifs soumis au jugement de l'enseignant

### 1.3 Contexte

L'accessibilité des IA génératives grand public (ChatGPT, Le Chat, Gemini…) crée un risque structurel d'envoi de bulletins non pseudonymisés à des services hors UE, sans base légale ni information des familles. Chiron propose une alternative conforme intégrant pseudonymisation automatique, hébergement européen et validation humaine.

### 1.4 Base légale suggérée

**Art. 6(1)(e) du RGPD — Mission d'intérêt public.** La préparation des conseils de classe relève de la mission de service public éducatif (Code de l'éducation, articles L. 111-1 et suivants). La CNIL confirme que l'utilisation de systèmes d'IA dans un cadre pédagogique peut reposer sur cette base légale (FAQ CNIL, juin 2025).

Le droit d'opposition (Art. 21 RGPD) s'applique : les parents peuvent s'opposer au traitement pour des raisons tenant à la situation particulière de leur enfant. La synthèse est alors rédigée manuellement par l'enseignant.

---

## 2. Responsabilités

| Acteur | Rôle RGPD | Responsabilité |
|--------|-----------|----------------|
| Chef d'établissement / DASEN | **Responsable de traitement** | Autorise l'usage, réalise/complète l'AIPD, informe les familles, gère les droits |
| Enseignant | Utilisateur | Utilise l'outil sous l'autorité du RT, vérifie et valide les synthèses |
| Chiron (logiciel open source) | Fournisseur de l'outil | Fournit cette fiche technique, documente l'architecture, intègre la privacy by design |
| Mistral AI (par défaut) | Sous-traitant (Art. 28 RGPD) | Traite les données pseudonymisées selon son [DPA](https://legal.mistral.ai/terms/data-processing-addendum), hébergement UE |

---

## 3. Données personnelles et flux

### 3.1 Schéma des flux

```
┌─────────────────────────────────────────────────────────────────────┐
│                     POSTE DE L'ENSEIGNANT (local)                   │
│                                                                     │
│  PDF Bulletin ──► Flair NER (local) ──► Données pseudonymisées       │
│  (PRONOTE)        Pseudonymisation       Noms → ELEVE_XXX            │
│                   locale                Notes → niveaux LSU          │
│                                                                     │
│  ┌─────────────┐  ┌───────────────┐  ┌────────────────────┐        │
│  │ chiron.db   │  │ privacy.db    │  │ Validation humaine │        │
│  │ (données    │  │ (mapping      │  │ obligatoire avant  │        │
│  │ pseudonym.) │  │ identités)    │  │ export             │        │
│  └─────────────┘  └───────────────┘  └────────────────────┘        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                  Données PSEUDONYMISÉES uniquement
                  (appréciations + niveaux LSU)
                           │
                           ▼
              ┌────────────────────────┐
              │   API Mistral AI       │
              │   Hébergement UE 🇪🇺    │
              │   DPA RGPD conforme    │
              │   Entraînement désactivé│
              └────────────────────────┘
                           │
                   Synthèse pseudonymisée
                           │
                           ▼
              ┌────────────────────────┐
              │  Dépseudonymisation    │
              │  locale + export       │
              │  (noms réels restaurés)│
              └────────────────────────┘
```

### 3.2 Données traitées localement uniquement (jamais transmises à l'IA)

| Donnée | Justification de la non-transmission |
|--------|--------------------------------------|
| Nom, prénom | Pseudonymisé en `ELEVE_XXX` ; seul le pseudonyme est transmis |
| Genre (F/G) | Stocké localement ; le LLM déduit le genre depuis les accords grammaticaux des appréciations |
| Absences, retards | Non pertinents pour la synthèse IA |
| Engagements (délégué, etc.) | Non transmis |
| Nom des professeurs | Non transmis |
| Nom de l'établissement | Non transmis |
| Classe (niveau, groupe) | Non transmis |
| Année scolaire, trimestre | Non transmis |

### 3.3 Données transmises à l'API LLM (pseudonymisées)

| Donnée | Forme transmise | Justification |
|--------|-----------------|---------------|
| Identité élève | `ELEVE_XXX` (pseudonyme) | Nécessaire pour structurer la synthèse |
| Moyennes par matière | Catégorisées en niveaux de maîtrise LSU (4 niveaux) | Minimisation : la note exacte n'est pas transmise |
| Appréciations enseignantes | Texte pseudonymisé (noms propres remplacés par pipeline 3 passes : regex + Flair NER + fuzzy) | Nécessaire pour la génération de la synthèse |

### 3.4 Limites connues de la pseudonymisation

Les appréciations enseignantes, même pseudonymisées, peuvent contenir des éléments indirectement identifiants non détectés par le modèle NER : situation familiale ou médicale mentionnée par un enseignant, événement personnel, contexte unique. Ces informations constituent un risque résiduel de ré-identification traité en section 6.1. La validation humaine inclut une vérification de ces éléments.

---

## 4. Mesures de protection

### 4.1 Privacy by design

| Mesure | Description | Article RGPD |
|--------|-------------|--------------|
| **Fail-safe à l'import** | Si le PDF ne correspond pas au format attendu (nom non détecté, aucune matière extraite), l'import est bloqué — aucune donnée n'est stockée ni transmise au LLM | Art. 25 |
| **Pseudonymisation NER** | Pipeline 3 passes local (regex + Flair NER + fuzzy) détecte et remplace les noms/prénoms avant tout envoi cloud | Art. 25, 32 |
| **Catégorisation LSU** | Les notes numériques sont converties en niveaux de maîtrise (4 niveaux) avant envoi | Art. 5(1)(c) — minimisation |
| **Absence de profilage** | Aucune catégorisation automatisée des élèves | Art. 5(1)(c), 22 |
| **Stockage local** | DuckDB fichier local, aucune donnée en cloud | Art. 32 |
| **Séparation des bases** | Le mapping identités (`privacy.duckdb`) est séparé des données pédagogiques (`chiron.duckdb`) | Art. 25, 32 |
| **Suppression en cascade** | La suppression efface données + mappings simultanément | Art. 5(1)(e) |
| **Effacement automatique** | Les données de plus de 30 jours sont supprimées au lancement | Art. 5(1)(e) |
| **Minimisation du stockage** | Le texte brut PDF n'est pas persisté ; seules les données structurées sont stockées | Art. 5(1)(c) |
| **Logs sans données nominatives** | Les logs de niveau INFO (défaut) ne contiennent jamais de données nominatives | Art. 25 |

### 4.2 Supervision humaine

| Mesure | Description |
|--------|-------------|
| **Validation obligatoire** | Aucune synthèse ne peut être exportée sans validation explicite par l'enseignant |
| **Vérification des données résiduelles** | L'enseignant vérifie qu'aucune information identifiante n'a échappé à la pseudonymisation (noms propres, éléments contextuels) |
| **Retrait des données sensibles** | L'enseignant vérifie l'absence de données Art. 9 (santé, handicap, situation familiale) dans la synthèse |
| **Modification libre** | L'enseignant peut modifier entièrement la synthèse avant validation |
| **Few-shot contrôlé** | Les exemples de calibration sont choisis par l'enseignant |

### 4.3 Sécurité technique

| Mesure | Description |
|--------|-------------|
| Clé API | Stockée dans `.env` local, jamais versionnée ni transmise |
| Communication API | HTTPS (TLS 1.2+) |
| Application locale | Écoute sur `127.0.0.1`, jamais exposée au réseau |
| SQL paramétré | Données utilisateur protégées par placeholders |
| Code source ouvert | Auditable par le RT, le DPO ou tout tiers — licence Apache 2.0 |

---

## 5. Sous-traitant LLM

### 5.1 Mistral AI (configuration par défaut)

- **Société française**, hébergement en Union européenne
- **DPA RGPD** : [legal.mistral.ai/terms/data-processing-addendum](https://legal.mistral.ai/terms/data-processing-addendum)
- **Désactivation de l'entraînement** : l'enseignant doit désactiver la réutilisation des données dans la console Mistral (Admin Console > Privacy > off)
- **Rétention** : aucune rétention au-delà du traitement de la requête (si entraînement désactivé). Une rétention technique temporaire à des fins de détection d'abus peut s'appliquer selon les conditions du DPA en vigueur
- **Sous-traitance ultérieure** : Mistral AI peut recourir à des sous-traitants (hébergeurs cloud). La liste est documentée dans leur DPA

### 5.2 Configuration multi-provider (OpenAI, Anthropic)

> **⚠️ Avertissement** : L'outil permet en configuration avancée l'utilisation d'OpenAI et Anthropic. Ces fournisseurs hébergent leurs services **hors Union européenne**. Leur utilisation implique un transfert de données pseudonymisées hors UE et nécessite une **réévaluation de l'AIPD**, incluant la vérification des garanties de transfert (Art. 44-49 RGPD, clauses contractuelles types ou décision d'adéquation).

Le RT doit s'assurer que seul le fournisseur autorisé est configuré sur les postes des enseignants.

---

## 6. Éléments pour l'analyse des risques

Les risques ci-dessous sont identifiés par l'équipe Chiron et documentés avec les mesures d'atténuation intégrées à l'outil. Le RT doit les évaluer dans le contexte de son établissement et compléter l'analyse avec les risques locaux (sécurité du poste, accès physique, etc.).

### 6.1 Ré-identification et données sensibles dans les appréciations

**Description** : Les appréciations, même pseudonymisées, peuvent contenir des éléments indirectement identifiants ou des données Art. 9 (santé, handicap, situation familiale) mentionnées incidemment par un enseignant.

**Gravité** : Importante (mineurs, données potentiellement sensibles)

**Mesures intégrées** : (1) L'enseignant vérifie et retire les éléments sensibles lors de la validation (2) Entraînement Mistral désactivé (3) Le LLM ne dispose pas du nom de l'établissement, de la classe ni de l'année scolaire (4) DPA Mistral interdisant la réutilisation.

### 6.2 Fuite de données via l'API LLM

**Description** : Interception des données en transit ou compromission du service Mistral AI.

**Gravité** : Modérée (données pseudonymisées, impact limité)

**Mesures intégrées** : (1) HTTPS obligatoire (2) Données pseudonymisées (3) DPA Mistral avec clauses de sécurité (4) Pas de données directement identifiantes en transit.

### 6.3 Accès non autorisé aux données locales

**Description** : Un tiers accède au poste de l'enseignant et aux bases DuckDB contenant le mapping de pseudonymisation.

**Gravité** : Critique (accès aux données nominatives complètes)

**Mesures intégrées** : (1) Effacement automatique à 30 jours (2) Séparation des bases (3) Suppression manuelle disponible.

**À évaluer par le RT** : Sécurité du poste (session Windows/macOS, chiffrement disque, antivirus), accès physique.

### 6.4 Qualité des synthèses / hallucinations

**Description** : Le LLM génère des informations inexactes ou invente des éléments non présents dans le bulletin.

**Gravité** : Importante (impact potentiel sur le parcours scolaire)

**Mesures intégrées** : (1) Validation humaine obligatoire (2) Calibration few-shot par l'enseignant (3) Prompt ancré dans les données fournies (4) L'enseignant connaît ses élèves.

### 6.5 Biais de genre dans les synthèses

**Description** : Le LLM reproduit ou amplifie des biais de genre présents dans les appréciations ou ses données d'entraînement.

**Gravité** : Modérée (impact sur l'équité de traitement)

**Mesures intégrées** : (1) Le prompt intègre une consigne de détection des biais de genre (2) Validation humaine (3) Le genre n'est pas transmis explicitement au LLM.

### 6.6 Conservation prolongée des données

**Description** : Les données sont conservées au-delà du nécessaire.

**Gravité** : Modérée

**Mesures intégrées** : (1) Effacement automatique à 30 jours au lancement (2) Suppression manuelle depuis la page Export (3) Export par copier-coller (pas de fichier généré).

### 6.7 Comparaison avec le risque de référence

| Scénario | Risque principal | Niveau |
|----------|-----------------|--------|
| **Sans outil dédié** — IA grand public non encadrée | Données nominatives complètes envoyées hors UE, sans pseudonymisation, sans DPA, sans information des familles | Critique |
| **Avec Chiron** — privacy by design | Risque résiduel de ré-identification contextuelle, atténué par la validation humaine | Faible |

---

## 7. Durées de conservation

| Données | Durée | Mécanisme |
|---------|-------|-----------|
| Données pseudonymisées (`chiron.duckdb`) | Durée du trimestre en cours (max 30 jours) | Effacement automatique au lancement + suppression manuelle (page Export) |
| Mapping identités (`privacy.duckdb`) | Idem | Suppression en cascade avec les données |
| Synthèses exportées | Aucune persistance fichier | Export par copier-coller uniquement |
| Données côté Mistral AI | Aucune rétention au-delà du traitement (si entraînement désactivé) | Conformément au DPA Mistral en vigueur |

---

## 8. Droits des personnes concernées

Le RT doit permettre l'exercice des droits suivants. Chiron fournit les mécanismes techniques correspondants.

| Droit | Article RGPD | Mécanisme dans Chiron |
|-------|-------------|----------------------|
| **Information** | Art. 13 | Le RT diffuse une note d'information aux familles (à rédiger par le RT/DPO) |
| **Opposition** | Art. 21 | L'enseignant rédige manuellement la synthèse pour l'élève concerné |
| **Accès** | Art. 15 | Les données sont consultables localement par l'enseignant et le RT |
| **Rectification** | Art. 16 | L'enseignant modifie la synthèse avant validation |
| **Effacement** | Art. 17 | Suppression manuelle à tout moment + effacement automatique à 30 jours |

---

## 9. Conformité au Règlement européen sur l'IA (RIA)

Le Règlement (UE) 2024/1689 identifie quatre types d'usage à haut risque dans l'éducation (Annexe III, point 3) : détermination d'accès/admission/affectation, évaluation automatisée des acquis (notation), surveillance d'examens, détection de comportements interdits.

Chiron est un **outil d'aide à la rédaction** dont le résultat est systématiquement revu par l'enseignant. Il ne relève pas directement de ces catégories. Toutefois, le RT doit veiller à ce que l'enseignant ne délègue pas son pouvoir d'appréciation à l'outil.

---

## Annexes

### A. Références techniques

- **DPA Mistral AI** : [legal.mistral.ai/terms/data-processing-addendum](https://legal.mistral.ai/terms/data-processing-addendum)
- **Code source Chiron** : [github.com/fdayde/chiron](https://github.com/fdayde/chiron)
- **Documentation technique** : `docs/architecture.md`
- **Flair NER** : flair/ner-french (modèle local, aucune donnée transmise)

### B. Références réglementaires et institutionnelles

- FAQ CNIL — Enseignant : [cnil.fr/fr/enseignant-usage-systeme-ia](https://www.cnil.fr/fr/enseignant-usage-systeme-ia)
- FAQ CNIL — Responsable de traitement : [cnil.fr/fr/education-mise-en-place-systeme-ia](https://www.cnil.fr/fr/education-mise-en-place-systeme-ia)
- Cadre d'usage de l'IA en éducation, Ministère de l'Éducation nationale, juin 2025
- Lignes directrices WP 248 (G29) sur les AIPD
