# JM Partners — Base de données Supabase v2.2

## Prérequis

- Projet Supabase actif
- Variables d'env configurées : `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

## Ordre d'exécution

Exécuter les fichiers dans l'ordre numérique dans **Supabase SQL Editor** :

```
001_jmpartners_v2.2.sql   — schéma complet (17 tables + index + triggers + RPC)
```

## Activer pgvector

Avant tout, activer l'extension dans le SQL Editor :

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Cette commande est incluse dans `001_jmpartners_v2.2.sql` mais peut aussi être
exécutée séparément depuis **Database → Extensions → vector**.

## Exécuter la migration

1. Ouvrir Supabase Dashboard → **SQL Editor**
2. Copier le contenu de `db/migrations/001_jmpartners_v2.2.sql`
3. Cliquer **Run** — les `CREATE TABLE IF NOT EXISTS` sont idempotents

## Données de test (dossier CIHAN)

Pour insérer les données de test du dossier pilote CIHAN :

```sql
-- Copier et exécuter db/seeds/001_jmpartners_cihan_test.sql
```

Le seed crée :
- 1 contact CIHAN (`compta@cihan.fr`)
- 1 dossier restauration actif
- 3 documents en attente OCR
- 2 écritures à valider
- 1 déclaration TVA mai 2026

## Tables créées

| Table | Rôle | Agent principal |
|-------|------|-----------------|
| `contacts` | Clients du cabinet | mail_handler, relance_handler |
| `dossiers` | Dossiers comptables | Tous agents |
| `documents` | Pièces justificatives | collecte, ocr, tri, ged |
| `journaux` | Audit log | Tous agents |
| `ecritures` | Écritures comptables proposées | presaisie, verificateur, lettrage |
| `ecritures_sage` | Écritures importées depuis Sage | miroir_sage |
| `syncs_sage` | Historique imports FEC | miroir_sage |
| `lettrages` | Paires règlement/facture | lettrage |
| `declarations_tva` | Déclarations TVA | tva_agent, echeance_agent |
| `acomptes_is` | Acomptes impôt sur les sociétés | acompte_is_agent |
| `provisions_fnp` | Provisions FNP/FAE décembre | fnp_fae_agent |
| `revision` | Anomalies comptables | revision_agent |
| `doublons_detectes` | Doublons documentaires | verificateur, revision |
| `apprentissage` | Patterns libellés bancaires | lettrage_agent |
| `ged_index` | Index archives GED | ged_agent |
| `collaborateurs` | Collaborateurs du cabinet | miroir_sage (rapport) |
| `embeddings` | Vecteurs pgvector historique FEC | presaisie_agent |

## Variables d'environnement requises

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
ANTHROPIC_API_KEY=<key>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<email>
SMTP_PASSWORD=<password>
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat_id>
OUTLOOK_MOCK_DIR=<path_local>        # optionnel, tests locaux
REGATE_API_KEY=<key>                 # optionnel
PENNYLANE_API_KEY=<key>              # optionnel
```

## RLS

RLS est **désactivé** sur toutes les tables — les agents utilisent la `service_key`
qui bypasse le RLS. Ne pas activer le RLS sans adapter les policies.

## Rollback

Aucun mécanisme de rollback automatique. En cas de problème :

```sql
-- Suppression complète (DANGER — perte de données)
DROP TABLE IF EXISTS embeddings, ged_index, apprentissage, doublons_detectes,
    revision, provisions_fnp, acomptes_is, declarations_tva, lettrages,
    syncs_sage, ecritures_sage, ecritures, journaux, documents,
    collaborateurs, dossiers, contacts CASCADE;
DROP EXTENSION IF EXISTS vector;
```
