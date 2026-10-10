# 🗺️ Roadmap : Application Operating System (Job Hunter Bot)

> **Projet :** Système d'automatisation des candidatures tech (DACH : Allemagne 🇩🇪, Suisse 🇨🇭, Luxembourg 🇱🇺)  
> **Candidat :** Wilfried Manfouo Fomekong (B.Sc. Angewandte Informatik, Hochschule Worms)  
> **Architecture :** n8n (Orchestrateur) + Telegram (Cockpit Décision) + FastAPI/Playwright (Bras Exécuteur) + Google Sheets (Source de Vérité)

---

## 📌 1. Bilan de l'existant (MVP v1.0 — Déjà Réalisé ✅)

- [x] **Ingestion multi-sources :** API REST Arbeitnow (Allemagne) + API SwissDevJobs (Suisse) fusionnées via nœud `Merge`.
- [x] **Filtrage intelligent :** Regex avancée sur les titres (`Werkstudent`, `Praktik`, `Python`, `DevOps`, `Automati`, `Software`) éliminant 84% du bruit.
- [x] **Déduplication (Idempotence) :** Interrogation préalable de Google Sheets (`Job_Hunter_DB`) pour bloquer les doublons avant tout appel IA.
- [x] **Moteur d'évaluation & Rédaction IA :** Modèle Groq Llama-3.1 générant le Score d'adéquation (sur 100), la justification, et un Anschreiben 100% en allemand calibré sur le standard professionnel.
- [x] **Cockpit Telegram interactif :** Envoi d'alertes enrichies avec boutons tactiles (`[ 🚀 POSTULER ]`, `[ ❌ IGNORER ]`, `[ 🌐 VOIR L'OFFRE ]`, `[ 💻 PORTFOLIO ]`).
- [x] **Worker Playwright Local :** Environnement virtuel Python (`venv`), API FastAPI (`worker_api.py`), profil candidat centralisé (`profil.json`), gestion des cookies, mapping sémantique des champs et téléversement de documents.

---

## 🔴 2. MUST-HAVE (Priorité 0 — À verrouiller pour la mise en production)

Ces éléments sont indispensables pour rendre le système 100% opérationnel et sécurisé au quotidien :

### 1. Boucler le clic Telegram avec l'API Playwright
- **Objectif :** Créer le workflow 2 dans n8n : `Telegram Trigger (Callback Query)` $\to$ `HTTP Request (POST http://host.docker.internal:8000/apply)`.
- **Résultat :** Dès que tu tapes sur `[ 🚀 POSTULER ]` sur ton smartphone, Chrome s'ouvre sur ton PC et commence à remplir le formulaire.

### 2. Dépôt physique de tes documents officiels
- **Objectif :** Placer tes 5 vrais PDF dans `d:\N8N\documents\` :
  - `cv.pdf`
  - `notenspiegel.pdf`
  - `immatrikulationsbescheinigung.pdf`
  - `praktikumszeugnis_pwo.pdf`
  - `aufenthaltstitel.pdf`

### 3. Fact-Checking en 2 passes de l'Anschreiben (Zéro Hallucination)
- **Objectif :** Ajouter une passe de vérification stricte dans n8n :
  - *Pass 1 :* Rédaction de la lettre.
  - *Pass 2 :* Vérification automatique contre `profil.json` pour garantir qu'aucune technologie ou responsabilité non exercée n'a été inventée par l'IA.

### 4. Automatisation temporelle (Schedule Trigger)
- **Objectif :** Remplacer le déclencheur manuel par un `Schedule Trigger` qui s'exécute chaque matin à **08h00** ou toutes les 6 heures.

---

## 🟡 3. NICE-TO-HAVE (Priorité 1 — Confort & Efficacité avancée)

Fonctionnalités améliorant drastiquement l'expérience utilisateur et le taux de succès :

### 1. Site Adapters spécifiques (Personio, Greenhouse, Workday)
- **Objectif :** Créer des sous-modules Playwright spécialisés pour les 3 portails d'emploi les plus fréquents en Allemagne :
  - `Personio` (très populaire dans les startups et PME allemandes).
  - `Workday` (utilisé par BMW, Bosch, grands groupes).
  - `Greenhouse / Lever`.

### 2. Answer Engine (Gestion des questions récurrentes)
- **Objectif :** Base de réponses pré-enregistrées dans `profil.json` pour répondre automatiquement aux questions pièges des formulaires :
  - Date de disponibilité : *« Zum nächstmöglichen Zeitpunkt / ab sofort »*
  - Statut étudiant : *« Ja, ordentlich immatrikuliert an der Hochschule Worms »*
  - Permis de travail : *« Gültiger Aufenthaltstitel mit Arbeitserlaubnis für studentische Beschäftigung vorhanden »*
  - Prétentions salariales pour stage : *« Nach Vereinbarung / Tarif »*

### 3. Génération dynamique de PDF pour l'Anschreiben
- **Objectif :** Convertir le texte HTML de l'Anschreiben directement en fichier PDF officiel mis en page (norme DIN 5008) pour que Playwright puisse aussi l'uploader dans le champ *« Anschreiben hochladen »*.

### 4. Envoi de la capture de confirmation sur Telegram
- **Objectif :** Après le pré-remplissage, le worker prend une capture d'écran du formulaire prêt et l'envoie sur Telegram : *« Formulaire prêt à 95% ! Vérifie ton écran. »*

---

## 🔵 4. ERWEITERUNG / EXTENSIONS FUTURES (Priorité 2 — Scale & Cloud)

Pour transformer ton projet en produit autonome et portable à l'échelle industrielle :

### 1. Déploiement Cloud 1-Clic (VPS Allemand / Hetzner)
- **Objectif :** Migrer n8n et le worker Playwright sur un petit serveur VPS en Allemagne via `Dockerfile.worker` et `docker-compose.yml`.
- **Mode Headless :** Le bot tourne sans écran 24/7 et tout se pilote depuis Telegram.

### 2. Mode Manuel par Commande Telegram (`/add <URL>`)
- **Objectif :** Quand tu tombes toi-même sur une annonce LinkedIn ou StepStone sur ton téléphone :
  - Tu partages le lien à ton bot Telegram : `/add https://...`
  - Le bot scrape l'offre, l'évalue, génère le dossier et te renvoie les boutons de candidature.

### 3. Migration Base de données vers PostgreSQL
- **Objectif :** Remplacer Google Sheets par une vraie base PostgreSQL (déjà intégrable dans Docker Compose) avec historique complet des candidatures, journal d'événements et métriques de conversion.

### 4. Lifecycle & Relances automatiques (Application Monitor)
- **Objectif :** 
  - Détection automatique des e-mails de refus ou d'invitation à un entretien via Gmail Trigger.
  - Alerte de relance automatique à J+14 sur Telegram si aucune réponse n'a été reçue.

---

## 📅 Ordre d'Exécution Recommandé

| Phase | Tâche | Durée estimée | Impact |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Lier le bouton Telegram au Worker Playwright (`Action Telegram`) | 15 min | 🔥 Immédiat |
| **Phase 2** | Déposer tes 5 PDF dans `documents/` et tester 1 remplissage réel | 10 min | 🔥 Immédiat |
| **Phase 3** | Configurer le `Schedule Trigger` (08h00 quotidien) | 5 min | 🚀 Autonomie |
| **Phase 4** | Implémenter l'Answer Engine dans `worker_api.py` | 30 min | ⚡ Gain de temps |
| **Phase 5** | Containeriser avec `Dockerfile.worker` pour le Cloud | Plus tard | ☁️ Scalabilité |
