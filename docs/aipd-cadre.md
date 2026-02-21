# AIPD-Cadre — Chiron

> **Analyse d'Impact relative à la Protection des Données (AIPD)**
> Document-cadre à destination des responsables de traitement (chefs d'établissement, DASEN)

| | |
|---|---|
| **Outil** | Chiron — Assistant IA pour la préparation des conseils de classe |
| **Version du document** | 1.1 |
| **Date** | _[À compléter par le RT]_ |
| **Auteur du document-cadre** | Équipe Chiron (fournisseur de l'outil) |
| **Responsable de traitement** | _[Chef d'établissement / DASEN — à compléter]_ |
| **DPO académique** | _[À compléter — coordonnées sur education.gouv.fr]_ |

---

## Objet du document

Ce document constitue une **AIPD-cadre** au sens de la recommandation de la CNIL (FAQ « Responsable de traitement : comment mettre en place des systèmes d'IA dans l'éducation ? », juin 2025). Il contient les éléments communs du traitement mis en œuvre par l'outil Chiron. Le responsable de traitement (RT) doit le compléter avec les éléments propres à son établissement (sections marquées 📝).

### Pourquoi une AIPD est-elle nécessaire ?

Le traitement mis en œuvre par Chiron réunit au moins trois critères identifiés par le G29 (lignes directrices WP 248) et repris par la CNIL comme déclencheurs d'une AIPD obligatoire (Art. 35 RGPD) :

1. **Personnes vulnérables** — Les données concernent des élèves, la plupart du temps mineurs
2. **Usage innovant** — Recours à l'IA générative pour la production de synthèses pédagogiques
3. **Évaluation de personnes** — Les synthèses constituent une forme d'appréciation du parcours scolaire

### Références réglementaires et institutionnelles

- Règlement (UE) 2016/679 (RGPD), en particulier les articles 35 et 36
- Règlement (UE) 2024/1689 sur l'intelligence artificielle (RIA)
- Loi n° 78-17 du 6 janvier 1978 modifiée (Informatique et Libertés)
- Cadre d'usage de l'IA en éducation, Ministère de l'Éducation nationale, juin 2025
- FAQ CNIL « Enseignant : comment utiliser un système d'IA » et « Responsable de traitement », juin 2025

---

## 1. Description du traitement

### 1.1 Finalité

Aider les enseignants à préparer les conseils de classe en générant des **projets de synthèses trimestrielles** à partir des bulletins scolaires, dans le respect de la réglementation sur la protection des données personnelles.

Les synthèses générées sont des **propositions** soumises à la relecture, la modification et la validation obligatoire de l'enseignant avant tout export. L'outil ne se substitue pas au jugement professionnel de l'enseignant.

**L'outil ne produit aucune catégorisation automatisée des élèves** : pas de scoring comportemental, pas de profilage, pas d'étiquetage par catégorie. Les sorties sont exclusivement des textes narratifs (synthèses, signaux factuels, pistes de travail) soumis au jugement de l'enseignant.

### 1.2 Contexte et justification

L'accessibilité croissante des IA génératives grand public (ChatGPT, Le Chat, Gemini, etc.) crée un **risque structurel** de traitement non encadré de données scolaires nominatives par des services non conformes au RGPD. En l'absence d'outil dédié conforme, ce risque est susceptible de se matérialiser par l'envoi de bulletins non pseudonymisés à des services hébergés hors UE, sans base légale, sans information des familles et sans traçabilité.

Chiron s'inscrit dans une démarche de **privacy by design** (Art. 25 RGPD), offrant une alternative conforme qui intègre la pseudonymisation automatique, le choix d'un hébergeur européen et la validation humaine systématique.

### 1.3 Base légale

**Art. 6(1)(e) du RGPD — Mission d'intérêt public**

La préparation des conseils de classe et la rédaction de synthèses scolaires relèvent de la mission de service public éducatif confiée aux établissements scolaires (Code de l'éducation, articles L. 111-1 et suivants). La CNIL confirme que l'utilisation de systèmes d'IA dans un cadre pédagogique peut reposer sur cette base légale (FAQ CNIL, juin 2025).

La pseudonymisation préalable à l'envoi cloud et la catégorisation des notes en niveaux de maîtrise (échelle LSU) constituent des mesures de **minimisation** (Art. 5(1)(c) RGPD) proportionnées à cette finalité.

> **Droit d'opposition (Art. 21 RGPD)** : Les parents et/ou les élèves peuvent s'opposer au traitement de leurs données par Chiron pour des raisons tenant à leur situation particulière. Le RT apprécie la suite à donner à cette demande.

### 1.4 Responsabilités

| Acteur | Rôle RGPD | Responsabilité |
|--------|-----------|----------------|
| Chef d'établissement (2nd degré) / DASEN (1er degré) | **Responsable de traitement** | Autorise l'usage, réalise/complète l'AIPD, informe les familles, gère les droits |
| Enseignant | Utilisateur | Utilise l'outil sous l'autorité du RT, vérifie et valide les synthèses, signale les anomalies |
| Chiron (logiciel open source) | Fournisseur de l'outil | Fournit l'AIPD-cadre, documente l'architecture, intègre la privacy by design |
| Mistral AI (par défaut) | Sous-traitant (au sens de l'Art. 28 RGPD) | Traite les données pseudonymisées selon son DPA, hébergement UE |

📝 **À compléter par le RT** :

- Nom et coordonnées du responsable de traitement : _____
- Coordonnées du DPO académique : _____
- Date d'autorisation de l'outil : _____

---

## 2. Description des flux de données

### 2.1 Schéma des flux

```
┌─────────────────────────────────────────────────────────────────────┐
│                     POSTE DE L'ENSEIGNANT (local)                   │
│                                                                     │
│  PDF Bulletin ──► CamemBERT (NER) ──► Données pseudonymisées        │
│  (PRONOTE)        Pseudonymisation      Noms → ELEVE_XXX            │
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

### 2.2 Inventaire des données personnelles

#### Données traitées localement uniquement (jamais transmises à l'IA)

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

#### Données transmises à l'API LLM (pseudonymisées)

| Donnée | Forme transmise | Justification |
|--------|-----------------|---------------|
| Identité élève | `ELEVE_XXX` (pseudonyme) | Nécessaire pour structurer la synthèse |
| Moyennes par matière | Catégorisées en niveaux de maîtrise LSU (4 niveaux) | Minimisation : la note exacte n'est pas transmise |
| Appréciations enseignantes | Texte pseudonymisé (noms propres remplacés) | Nécessaire pour la génération de la synthèse |

#### Limites connues de la pseudonymisation

Les appréciations enseignantes, même pseudonymisées, peuvent contenir des éléments indirectement identifiants qui ne sont pas détectés par le modèle NER : situation familiale ou médicale mentionnée par un enseignant, événement personnel (« a brillé au concours de robotique »), contexte unique permettant de déduire l'identité de l'élève. Ces informations contextuelles constituent un **risque résiduel de ré-identification** traité en section 4.1. La validation humaine inclut une vérification explicite de ces éléments.

### 2.3 Durée de conservation

| Données | Durée | Mécanisme |
|---------|-------|-----------|
| Données pseudonymisées (`chiron.duckdb`) | Au maximum la durée du trimestre scolaire en cours | Suppression manuelle par l'enseignant (page Export) |
| Mapping identités (`privacy.duckdb`) | Au maximum la durée du trimestre scolaire en cours | Suppression en cascade avec les données |
| Synthèses exportées (CSV) | Responsabilité du RT | Hors périmètre de l'outil |
| Données côté Mistral AI | Aucune rétention au-delà du traitement de la requête (si entraînement désactivé). Une rétention technique temporaire à des fins de détection d'abus peut s'appliquer selon les conditions du DPA Mistral en vigueur. | Conformément au DPA Mistral |

> **Note** : La purge est déclenchée manuellement par l'enseignant après le conseil de classe. L'outil affiche un rappel de purge mais ne supprime pas automatiquement les données. Le RT peut définir une procédure interne pour s'assurer que la purge est effectuée dans les délais.

📝 **À compléter par le RT** :

- Politique de conservation des exports CSV : _____
- Fréquence de purge prévue : _____
- Procédure de vérification de la purge effective : _____

---

## 3. Mesures de protection existantes

### 3.1 Privacy by design

| Mesure | Description | Article RGPD |
|--------|-------------|--------------|
| **Pseudonymisation NER** | Modèle CamemBERT (local) détecte et remplace les noms/prénoms avant tout envoi cloud | Art. 25, 32 |
| **Catégorisation LSU** | Les notes numériques sont converties en niveaux de maîtrise (4 niveaux) avant envoi | Art. 5(1)(c) — minimisation |
| **Absence de profilage** | Aucune catégorisation automatisée des élèves (pas de scoring comportemental, pas de label) | Art. 5(1)(c), 22 |
| **Stockage local** | DuckDB fichier local, aucune donnée stockée en cloud | Art. 32 |
| **Séparation des bases** | Le mapping identités (`privacy.duckdb`) est séparé des données pédagogiques | Art. 25, 32 |
| **Suppression en cascade** | La purge supprime données + mappings simultanément | Art. 5(1)(e) — limitation conservation |
| **Hébergement UE** | Mistral AI, société française, hébergement UE, DPA conforme | Art. 44-49 — transferts |
| **Désactivation entraînement** | Procédure documentée pour désactiver la réutilisation des données par Mistral | Art. 5(1)(b) — limitation finalités |

### 3.2 Supervision humaine

| Mesure | Description |
|--------|-------------|
| **Validation obligatoire** | Aucune synthèse ne peut être exportée sans validation explicite par l'enseignant |
| **Vérification des données personnelles résiduelles** | L'enseignant vérifie à la validation qu'aucune information identifiante n'a échappé à la pseudonymisation (noms propres mais aussi éléments contextuels : situation familiale, médicale, événements personnels) |
| **Retrait des données sensibles** | L'enseignant est invité à retirer ou reformuler les mentions de données sensibles (état de santé, handicap, situation familiale protégée) dans les appréciations source avant import, ou à vérifier leur absence dans la synthèse générée lors de la validation |
| **Modification libre** | L'enseignant peut modifier entièrement la synthèse avant validation |
| **Few-shot contrôlé** | Les exemples de calibration sont choisis par l'enseignant, pas par le système |
| **Horodatage** | La validation est tracée (date/heure) dans la base locale |

### 3.3 Sécurité technique

| Mesure | Description |
|--------|-------------|
| Clé API | Stockée dans `.env` local, jamais versionnée ni transmise |
| Communication API | HTTPS (TLS 1.2+) |
| Pas de serveur distant | L'application tourne intégralement sur le poste de l'enseignant |
| Code source ouvert | Auditable par le RT, le DPO ou tout tiers |

### 3.4 Sous-traitance ultérieure

Mistral AI peut recourir à des sous-traitants ultérieurs (hébergeurs cloud) pour l'exécution de ses services. La liste des sous-traitants et les garanties associées sont documentées dans le [DPA Mistral AI](https://legal.mistral.ai/terms/data-processing-addendum). Le RT est invité à consulter ce document et à s'assurer que les garanties sont compatibles avec ses exigences.

### 3.5 Périmètre fournisseur — Configuration multi-provider

> **⚠️ Cette AIPD couvre exclusivement la configuration par défaut : Mistral AI (hébergement UE).**
>
> L'outil permet en configuration avancée l'utilisation d'autres fournisseurs LLM (OpenAI, Anthropic). Ces fournisseurs hébergent leurs services **hors Union européenne**. Leur utilisation implique un transfert de données pseudonymisées hors UE et nécessite une **réévaluation de la présente AIPD**, incluant la vérification des garanties de transfert (Art. 44-49 RGPD, clauses contractuelles types ou décision d'adéquation) et la mise à jour du DPA applicable.
>
> Le RT doit s'assurer que seul le fournisseur autorisé est configuré sur les postes des enseignants.

📝 **À compléter par le RT** :

- Mesures de sécurité du poste de l'enseignant (antivirus, chiffrement disque, politique de mots de passe) : _____
- Accès physique au poste : _____

---

## 4. Analyse des risques

### 4.1 Risque R1 — Ré-identification et données sensibles dans les appréciations

| | |
|---|---|
| **Description** | Les appréciations enseignantes, même pseudonymisées, peuvent contenir des éléments indirectement identifiants (situation familiale, médicale, événement personnel, contexte unique). Ces éléments ne sont pas détectés par le modèle NER. Certaines appréciations peuvent également contenir de manière incidente des **données relevant de l'Art. 9 RGPD** (état de santé, situation familiale protégée, handicap). Le traitement n'a pas pour finalité le traitement de ces données sensibles, mais leur présence dans les appréciations source constitue un risque. |
| **Gravité** | 🟠 Importante — concerne des mineurs, données potentiellement sensibles (Art. 9) |
| **Vraisemblance** | 🟡 Modérée — nécessite un accès aux données côté Mistral ET une connaissance du contexte scolaire local |
| **Mesures d'atténuation** | (1) **L'enseignant doit retirer ou reformuler les éléments sensibles** (données médicales, familiales, handicap) des appréciations source avant import, ou à défaut vérifier leur absence lors de la validation (2) Validation humaine avec avertissement explicite sur les données contextuelles (3) Entraînement Mistral désactivé (pas de rétention) (4) DPA Mistral interdisant la réutilisation (5) Le LLM ne dispose pas du nom de l'établissement, de la classe ni de l'année scolaire |
| **Risque résiduel** | 🟢 Faible après atténuation |

### 4.2 Risque R2 — Fuite de données via l'API LLM

| | |
|---|---|
| **Description** | Interception des données en transit ou compromission du service Mistral AI. |
| **Gravité** | 🟡 Modérée — données pseudonymisées, impact limité |
| **Vraisemblance** | 🟢 Faible — communication HTTPS, Mistral certifié, hébergement UE |
| **Mesures d'atténuation** | (1) HTTPS obligatoire (2) Données pseudonymisées (3) DPA Mistral avec clauses de sécurité (4) Pas de données directement identifiantes en transit |
| **Risque résiduel** | 🟢 Faible |

### 4.3 Risque R3 — Accès non autorisé aux données locales

| | |
|---|---|
| **Description** | Un tiers accède au poste de l'enseignant et aux bases DuckDB contenant les données nominatives et le mapping de pseudonymisation. |
| **Gravité** | 🔴 Critique — accès aux données nominatives complètes |
| **Vraisemblance** | 🟡 Variable selon la sécurité du poste |
| **Mesures d'atténuation** | (1) Purge trimestrielle (réduction de la fenêtre d'exposition) (2) Séparation des bases (3) _Mesures de sécurité du poste — à compléter par le RT_ |
| **Risque résiduel** | 📝 À évaluer par le RT selon le contexte local |

### 4.4 Risque R4 — Qualité des synthèses / hallucinations

| | |
|---|---|
| **Description** | Le LLM génère des informations inexactes ou invente des éléments non présents dans le bulletin (hallucination). |
| **Gravité** | 🟠 Importante — impact potentiel sur le parcours scolaire de l'élève |
| **Vraisemblance** | 🟡 Modérée — inhérent aux modèles génératifs |
| **Mesures d'atténuation** | (1) Validation humaine obligatoire avant export (2) Calibration few-shot par l'enseignant (3) Prompt conçu pour ancrer la génération dans les données fournies (4) L'enseignant connaît ses élèves et peut détecter les erreurs |
| **Risque résiduel** | 🟢 Faible après validation humaine |

### 4.5 Risque R5 — Biais de genre dans les synthèses

| | |
|---|---|
| **Description** | Le LLM reproduit ou amplifie des biais de genre présents dans les appréciations source ou dans ses données d'entraînement. |
| **Gravité** | 🟡 Modérée — impact sur l'équité de traitement |
| **Vraisemblance** | 🟡 Modérée — biais documentés dans les LLM |
| **Mesures d'atténuation** | (1) Le prompt intègre une consigne de détection des biais de genre (2) Validation humaine (3) Le genre n'est pas transmis explicitement au LLM |
| **Risque résiduel** | 🟢 Faible après atténuation |

### 4.6 Risque R6 — Non-purge des données après le conseil de classe

| | |
|---|---|
| **Description** | L'enseignant oublie de purger les données après le conseil de classe, prolongeant la durée de conservation au-delà du nécessaire. |
| **Gravité** | 🟡 Modérée — augmente la fenêtre d'exposition en cas de compromission du poste |
| **Vraisemblance** | 🟡 Modérée — la purge est manuelle et dépend de la rigueur de l'utilisateur |
| **Mesures d'atténuation** | (1) Rappel de purge affiché dans l'interface après l'export (2) Procédure de purge documentée (3) Le RT peut instituer un rappel ou une vérification périodique |
| **Risque résiduel** | 🟢 Faible si le RT met en place une procédure de suivi |

### 4.7 Comparaison avec le risque de référence (absence d'outil dédié)

| Scénario | Risque principal | Niveau |
|----------|-----------------|--------|
| **Sans Chiron** — Utilisation d'IA grand public non encadrée | Envoi de données nominatives complètes à des services hors UE, sans pseudonymisation, sans DPA, sans traçabilité, sans information des familles | 🔴 Critique |
| **Avec Chiron** — Outil dédié privacy by design | Risque résiduel de ré-identification contextuelle, atténué par la validation humaine et l'absence de rétention | 🟢 Faible |

---

## 5. Droits des personnes concernées

### 5.1 Information (Art. 13/14 RGPD)

Le RT doit informer les parents/représentants légaux et les élèves de l'utilisation de Chiron. Un modèle de note d'information est fourni séparément (voir `docs/note-information-familles.md`).

L'information doit couvrir :
- L'identité du RT et les coordonnées du DPO
- La finalité du traitement et la base légale
- Les catégories de données traitées et les mesures de pseudonymisation
- Les destinataires (Mistral AI en tant que sous-traitant, données pseudonymisées uniquement)
- La durée de conservation
- Les droits des personnes (accès, rectification, opposition, effacement)
- Le droit d'introduire une réclamation auprès de la CNIL

Conformément au cadre d'usage de l'IA en éducation du Ministère (juin 2025), l'utilisation de l'IA doit faire l'objet d'une **communication explicite** sur son rôle et la façon dont elle a été utilisée.

**Vecteurs de diffusion recommandés** : note via l'ENT (espace numérique de travail), courrier joint au bulletin du premier trimestre, ou présentation lors de la réunion de rentrée. Le RT choisit le vecteur le plus adapté à son contexte.

### 5.2 Droit d'opposition (Art. 21 RGPD)

Les parents et/ou élèves peuvent s'opposer au traitement pour des raisons tenant à leur situation particulière. Le RT apprécie la demande. En cas d'opposition acceptée, l'enseignant rédige la synthèse manuellement pour l'élève concerné.

### 5.3 Droit d'accès et de rectification (Art. 15, 16 RGPD)

Les parents peuvent demander l'accès aux données traitées et la rectification des synthèses. Les synthèses étant validées par l'enseignant avant export, la rectification s'exerce auprès de l'enseignant et du RT.

### 5.4 Droit d'effacement (Art. 17 RGPD)

Les parents peuvent demander l'effacement des données de leur enfant. Les données locales peuvent être supprimées à tout moment par l'enseignant. Les données pseudonymisées transmises à Mistral AI ne sont pas conservées au-delà du traitement de la requête (sous réserve des conditions du DPA Mistral en vigueur). La purge trimestrielle garantit un effacement systématique de l'ensemble des données à l'issue de chaque période.

📝 **À compléter par le RT** :

- Modalités de réception des demandes d'exercice des droits : _____
- Personne en charge du traitement des demandes : _____
- Modalité d'information des familles choisie (note via ENT, courrier, réunion, etc.) : _____

---

## 6. Conformité au Règlement européen sur l'IA (RIA)

Le Règlement (UE) 2024/1689 identifie quatre types d'usage à haut risque dans l'éducation (Annexe III, point 3). Le cas d'usage de Chiron — aide à la rédaction de synthèses de conseil de classe — **ne relève pas directement** de ces catégories à haut risque qui concernent :

- a) La détermination de l'accès, l'admission ou l'affectation de personnes
- b) L'évaluation des acquis d'apprentissage (notation automatisée)
- c) La surveillance des examens
- d) La détection du comportement interdit des élèves

Chiron est un **outil d'aide à la rédaction** dont le résultat est systématiquement revu et modifié par l'enseignant. Il ne prend aucune décision automatisée au sens de l'Art. 22 RGPD et ne produit aucune catégorisation ou scoring des élèves. Toutefois, le RT doit veiller à ce que l'enseignant ne délègue pas son pouvoir d'appréciation à l'outil.

---

## 7. Plan d'action

📝 **À compléter et valider par le RT** :

| Action | Responsable | Échéance | Statut |
|--------|-------------|----------|--------|
| Compléter cette AIPD avec les éléments locaux | RT + DPO | Avant mise en service | ☐ |
| Informer les familles (note d'information) | RT | Avant mise en service | ☐ |
| Associer le DPO académique | RT | Avant mise en service | ☐ |
| Inscrire le traitement au registre des activités de traitement | RT | Avant mise en service | ☐ |
| Vérifier la désactivation de l'entraînement Mistral | Enseignant | Avant première utilisation | ☐ |
| Former l'enseignant à la vérification des données personnelles résiduelles | RT / Enseignant | Avant première utilisation | ☐ |
| Purger les données après chaque conseil de classe | Enseignant | Trimestrielle | ☐ |
| Vérifier que la purge a été effectuée | RT | Trimestrielle | ☐ |
| Réévaluer l'AIPD en cas de changement (provider, fonctionnalité, etc.) | RT + DPO | Annuelle ou événementielle | ☐ |

---

## 8. Avis

### Avis du DPO académique

📝 _[À compléter]_

Date : _____
Avis : ☐ Favorable ☐ Favorable avec réserves ☐ Défavorable

Observations : _____

### Décision du responsable de traitement

📝 _[À compléter]_

Date : _____
Décision : ☐ Mise en service autorisée ☐ Mise en service sous conditions ☐ Mise en service refusée

Conditions éventuelles : _____

Signature : _____

---

## Annexes

### A. Références techniques

- **DPA Mistral AI** : [legal.mistral.ai/terms/data-processing-addendum](https://legal.mistral.ai/terms/data-processing-addendum)
- **Code source Chiron** : [github.com/fdayde/chiron](https://github.com/fdayde/chiron)
- **Documentation technique** : `docs/architecture.md`
- **CamemBERT NER** : Jean-Baptiste/camembert-ner (modèle local, aucune donnée transmise)

### B. Cadre d'usage du Ministère

- Cadre d'usage de l'IA en éducation, Ministère de l'Éducation nationale, juin 2025
- FAQ CNIL — Enseignant : [cnil.fr/fr/enseignant-usage-systeme-ia](https://www.cnil.fr/fr/enseignant-usage-systeme-ia)
- FAQ CNIL — Responsable de traitement : [cnil.fr/fr/education-mise-en-place-systeme-ia](https://www.cnil.fr/fr/education-mise-en-place-systeme-ia)

### C. Modèle de note d'information aux familles

Voir `docs/note-information-familles.md` (document séparé).
