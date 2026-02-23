# Audit de sécurité — Chiron

**Date :** 2026-02-21 | **Auditeur :** Claude (audit automatisé assisté par le mainteneur)

---

## Contexte de déploiement

- **Application locale** : écoute sur `127.0.0.1`, jamais exposée au réseau
- **Mono-utilisateur** : un seul professeur principal sur son poste
- **Distribution autonome** : `.exe` PyInstaller
- **Données sensibles** : bulletins scolaires (RGPD applicable)

Ce contexte rend non applicables les vulnérabilités réseau classiques (authentification, CORS, CSRF, rate limiting HTTP, headers de sécurité, audit trail multi-utilisateur). L'analyse se concentre sur la **protection des données élèves** et la **propreté du dépôt public**.

---

## Mesures de sécurité en place

| Mesure | Détail |
|--------|--------|
| **Pseudonymisation NER** | CamemBERT local avant tout envoi cloud (noms, prénoms → `ELEVE_XXX`) |
| **Aucune donnée nominative au LLM** | Le cloud ne reçoit que des données pseudonymisées |
| **Catégorisation des notes** | Moyennes converties en niveaux LSU avant envoi |
| **Séparation des bases** | `privacy.duckdb` séparé de `chiron.duckdb`, cascade de suppression |
| **Effacement automatique (30j)** | Données expirées supprimées au lancement |
| **Suppression manuelle** | Suppression données + mappings après export |
| **Validation humaine** | Obligatoire avant export |
| **Provider UE** | Mistral AI, hébergé en UE, soumis au RGPD |
| **Rate limiting LLM** | Fenêtre glissante RPM sur les appels API |
| **SQL paramétré** | Données utilisateur protégées par placeholders (`?`) |
| **Secrets protégés** | `.env` dans `.gitignore`, `.env.example` fourni, aucune clé dans l'historique git |
| **Scan de dépendances** | Dependabot security updates activé par défaut (repo public GitHub) |

---

## Points analysés

### Risques acceptés (documentés)

**Noms de tables SQL interpolés** (`src/privacy/pseudonymizer.py`)
Le nom de table est une constante hardcodée (`mapping_identites` dans `config.py`), pas une entrée utilisateur. Les données utilisateur utilisent des placeholders paramétrés. Pas de vecteur d'injection exploitable.

**Version flottante du modèle** (`src/llm/config.py`)
`mistral-large-latest` est un choix délibéré pour bénéficier des améliorations automatiques.

### Sévérité basse

**Validation PDF limitée** (`src/api/routers/exports.py`)
Validations en place : content-type, taille max, extraction regex, erreur si 0 matières. Les PDF proviennent de Pronote (source fiable). Un PDF malformé provoquerait au pire un crash local.

### Non applicable (contexte localhost mono-utilisateur)

Authentification, contrôle d'accès, CORS, headers de sécurité, CSRF, timeout de session, audit trail, logs verbeux, chiffrement des fichiers temporaires.

---

## Conformité OWASP Top 10

| Catégorie | Statut |
|-----------|--------|
| A01 Broken Access Control | N/A — localhost mono-utilisateur |
| A02 Cryptographic Failures | Conforme — aucun secret dans l'historique git |
| A03 Injection | Risque accepté — identifiants SQL depuis config interne |
| A04 Insecure Design | Conforme |
| A05 Security Misconfiguration | N/A — pas de serveur exposé |
| A06 Vulnerable Components | Conforme — Dependabot security updates actif |
| A07 Authentication Failures | N/A |
| A08 Data Integrity Failures | Conforme — pipeline de pseudonymisation vérifié |
| A09 Logging & Monitoring | N/A |
| A10 SSRF | N/A |
