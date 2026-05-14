# LeadCommercial — Architecture

## Vue d'ensemble

LeadCommercial est un pipeline de qualification de leads BtoB qui tourne chaque nuit à 02h00 (Europe/Paris). Il identifie les entreprises françaises nouvellement créées susceptibles d'être clientes d'un cabinet comptable partenaire.

```
Sirene API → sirene_fetcher → lead_scorer → pappers_enricher → supabase_writer → telegram_notifier
                                                                      ↑
                                                                 (skip si lock)
```

---

## Structure des fichiers

```
apps/leadcommercial/
├── agents/
│   ├── __init__.py
│   ├── sirene_fetcher.py    # Etape 1 : fetch entreprises IDF
│   ├── lead_scorer.py       # Etape 2 : score 1 entreprise
│   ├── pappers_enricher.py  # Etape 3 : enrichit 1 lead
│   ├── supabase_writer.py   # Etape 4 : lock + insertion Supabase
│   └── telegram_notifier.py # Etape 5 : alerte Telegram
├── orchestrator.py          # Enchaîne les 5 agents, gère les erreurs
├── main.py                  # Scheduler APScheduler + flag --once
├── pipeline.py              # (legacy, conservé pour compatibilité)
├── sirene_client.py         # Client HTTP Sirene API (réutilisé par l'agent)
├── scorer.py                # Logique de scoring ICP (réutilisée par l'agent)
├── pappers_client.py        # Client HTTP Pappers API (réutilisé par l'agent)
└── supabase_client.py       # Client Supabase (réutilisé par les agents)
```

---

## Rôle de chaque composant

### `agents/sirene_fetcher.py`

**Fonction principale :** `fetch_idf_companies(params: SireneInput) -> list[CompanyRaw]`

Appelle `sirene_client.fetch_and_parse_idf` et retourne les établissements créés la veille, filtrés sur les 8 départements d'Île-de-France.

| TypedDict | Champs |
|-----------|--------|
| `SireneInput` | `max_results: int`, `date: str \| None` |
| `CompanyRaw` | `siren`, `siret`, `denomination`, `forme_juridique`, `code_naf`, `dept`, `commune`, `date_creation` |

---

### `agents/lead_scorer.py`

**Fonction principale :** `score_company(params: ScoreInput) -> ScoredLead`

Délègue à `scorer.score_lead`. Le `ScoredLead` contient `score`, `signal_type`, `scoring_details`, `qualified`, et des champs d'enrichissement vides (remplis à l'étape suivante).

| TypedDict | Champs |
|-----------|--------|
| `ScoreInput` | `company: CompanyRaw`, `signal_type: str`, `icp: IcpContext \| None` |
| `ScoredLead` | défini dans `scorer.py` |

**Règles de scoring (défaut) :**

| Signal | Score base |
|--------|------------|
| `creation` | 100 |
| `rattrapage` | 80 |
| `fiscal` | 80 |
| `intention` | 60 |

Bonus : secteur restauration +10, création < 7 j +10, < 14 j +5.  
Malus : forme juridique non prioritaire -10.  
Filtre éliminatoire : hors IDF → score = 0.

Toutes ces règles sont overridables via `IcpContext` (table `icps` Supabase).

---

### `agents/pappers_enricher.py`

**Fonction principale :** `enrich_lead(params: EnrichInput) -> PappersEnrichment`

Délègue à `pappers_client.fetch_enrichment`. Retourne les champs vides en cas d'erreur API (dégradation gracieuse).

| TypedDict | Champs |
|-----------|--------|
| `EnrichInput` | `siren: str` |
| `PappersEnrichment` | `dirigeant_nom`, `dirigeant_prenom`, `dirigeant_email`, `site_web`, `capital_social` |

---

### `agents/supabase_writer.py`

**Fonction principale :** `write_lead(params: WriteInput) -> bool`

Délègue à `supabase_client.persist_lead` qui vérifie le lock puis insère dans la table `leads` et crée une ligne dans `lead_locks`.

Retourne `False` si le SIREN est déjà lockée par un autre cabinet (lead ignoré, pas d'alerte).

| TypedDict | Champs |
|-----------|--------|
| `WriteInput` | `siren`, `denomination`, `forme_juridique`, `code_naf`, `commune`, `dept`, `date_creation`, `score`, `signal_type`, `dirigeant_*`, `site_web`, `capital_social` |

---

### `agents/telegram_notifier.py`

**Fonction principale :** `notify_lead(params: NotifyInput) -> bool`

Formate un message Markdown et l'envoie via l'API `sendMessage` de Telegram. Retourne `False` si `TELEGRAM_BOT_TOKEN` ou `TELEGRAM_CHAT_ID` est absent.

| TypedDict | Champs |
|-----------|--------|
| `NotifyInput` | tous les champs nécessaires au message : identification, score, dirigeant |

---

### `orchestrator.py`

**Fonction principale :** `run(date: str | None, dry_run: bool) -> list[LeadEnriched]`

Aucune logique métier. Enchaîne les 5 agents avec gestion d'erreur par étape :

```
1. fetch_idf_companies()          — échec → return []
2. score_company()                — échec → continue (lead suivant)
3. enrich_lead()                  — échec → enrichissement vide (lead conservé)
4. write_lead()     [skip si dry_run]  — échec → continue ; False → continue
5. notify_lead()    [skip si dry_run]  — échec → warning (lead déjà compté)
```

L'ICP Supabase est chargé **une seule fois** avant la boucle et passé à chaque `score_company`.

`dry_run=True` : les étapes 4 et 5 sont sautées, utile pour les tests en local.

| TypedDict | Description |
|-----------|-------------|
| `LeadEnriched` | Union de `CompanyRaw` + `ScoredLead` + `PappersEnrichment` |

---

### `main.py`

Point d'entrée unique. Expose :

- **`start_scheduler()`** : lance le `BlockingScheduler` APScheduler, déclenche `_run_job()` chaque nuit à 02:00 Europe/Paris avec un `misfire_grace_time` de 3600 s.
- **`_run_job()`** : appelle `orchestrator.run()` et capte toute exception vers Sentry.
- **`main(argv)`** : initialise logging + Sentry puis :
  - `--once` → exécution immédiate puis arrêt
  - (défaut) → `start_scheduler()`

```bash
# Exécution ponctuelle
python -m apps.leadcommercial.main --once

# Mode scheduler (Docker)
python -m apps.leadcommercial.main
```

---

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `SIRENE_API_TOKEN` | Oui | Clé API INSEE Sirene |
| `PAPPERS_API_KEY` | Non | Clé API Pappers (enrichissement désactivé si absent) |
| `SUPABASE_URL` | Oui | URL du projet Supabase |
| `SUPABASE_SERVICE_KEY` | Oui | Clé service Supabase (RLS bypass) |
| `CABINET_ID` | Non | UUID du cabinet — active le chargement ICP |
| `TELEGRAM_BOT_TOKEN` | Non | Token du bot Telegram (alertes désactivées si absent) |
| `TELEGRAM_CHAT_ID` | Non | ID du chat Telegram cible |
| `LEAD_SCORE_THRESHOLD` | Non | Score minimum pour qualifier un lead (défaut : 50) |
| `SENTRY_DSN` | Non | DSN Sentry pour la capture d'exceptions |
| `DOPPLER_ENVIRONMENT` | Non | Étiquette d'environnement Sentry (défaut : `dev`) |

---

## Guide : ajouter un agent

1. Créer `apps/leadcommercial/agents/mon_agent.py` avec :
   - Un `TypedDict` pour l'input
   - Un `TypedDict` pour l'output (ou réutiliser un existant)
   - Une fonction publique documentée
2. L'importer dans `orchestrator.py` et l'insérer dans la chaîne
3. Ajouter `tests/test_lc_agents_mon_agent.py` avec au minimum :
   - Test du cas nominal (mock du client sous-jacent)
   - Test de la dégradation gracieuse en cas d'erreur
4. Ajouter un test dans `test_lc_orchestrator.py` vérifiant que le nouvel agent est appelé / skippé correctement

---

## Schéma de données (Supabase)

Voir [`docs/leadcommercial/schema.sql`](schema.sql) pour le schéma complet des 9 tables.

Tables principales impliquées dans ce pipeline :

| Table | Rôle |
|-------|------|
| `icps` | Critères ICP par cabinet (secteurs, zones, scoring custom) |
| `leads` | Leads qualifiés insérés par `supabase_writer` |
| `lead_locks` | Verrou d'exclusivité par SIREN (1 cabinet par SIREN) |
