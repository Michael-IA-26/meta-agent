# Base de données JM Partners v2.2

Schéma Supabase PostgreSQL + pgvector pour le système de 13 agents autonomes.

## Architecture

| Couche | Tables |
|---|---|
| Cabinet | `utilisateurs`, `contacts`, `dossiers` |
| Chaîne documentaire | `documents`, `journaux`, `embeddings` |
| Comptabilité | `ecritures`, `ecritures_sage`, `syncs_sage`, `lettrages` |
| Fiscal | `declarations_tva`, `acomptes_is`, `provisions_fnp` |
| Qualité | `revision`, `doublons_detectes`, `apprentissage` |
| GED | `ged_index` |

**FK critique** : `dossiers.contact_id → contacts.id ON DELETE RESTRICT`  
Un contact ne peut pas être supprimé tant qu'il a des dossiers — archiver les dossiers d'abord.

---

## Prérequis

```bash
# Supabase CLI
brew install supabase/tap/supabase

# psql
brew install postgresql

# URL de connexion directe (Database → Settings → Connection string → URI)
export SUPABASE_DB_URL="postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
```

---

## Procédure d'application (5 étapes)

### Étape 1 — Dry run (test sans modification)

Vérifie la migration sans toucher à la base. Le ROLLBACK final annule tout.

```bash
psql $SUPABASE_DB_URL -f db/migrations/001_jmpartners_v2.2_DRY_RUN.sql
```

Résultat attendu :
```
NOTICE:  ✅ DRY RUN OK — migration v2.2 valide (ROLLBACK — aucune modification)
ROLLBACK
```

---

### Étape 2 — Application réelle

```bash
psql $SUPABASE_DB_URL -f db/migrations/001_jmpartners_v2.2.sql
```

Résultat attendu :
```
NOTICE:  ✅ MIGRATION v2.2 VALIDÉE — 17 tables + pgvector + enum + indexes OK
COMMIT
```

La migration est transactionnelle — si le DO BLOCK de vérification échoue, tout est annulé automatiquement.

---

### Étape 3 — Seed CIHAN (dossier pilote)

À exécuter après la migration, en développement ou staging uniquement.

```bash
psql $SUPABASE_DB_URL -f db/seeds/001_cihan.sql
```

Insère :
- 1 utilisateur (Michael Sadoun, michael@jmpartners.fr)
- 2 contacts CIHAN (gérant Mohamed Hassani + comptable interne Sophie Martin)
- 1 dossier TVA 2026, secteur restauration
- 3 documents en statut `en_attente_ocr` (facture achat, facture vente, relevé bancaire)
- 1 déclaration TVA mai-2026 en `pieces_manquantes`

---

### Étape 4 — Vérification post-migration

```bash
# 17 tables présentes
psql $SUPABASE_DB_URL -c "\dt public.*"

# Enum statut_document
psql $SUPABASE_DB_URL -c "SELECT enum_range(NULL::statut_document);"

# pgvector activé
psql $SUPABASE_DB_URL -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

# Index critiques
psql $SUPABASE_DB_URL -c "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY 1;"

# Seed CIHAN OK
psql $SUPABASE_DB_URL -c "SELECT nom, type_document, statut FROM documents WHERE dossier_id='cihan-0000-0000-0000-dossier00001';"
```

---

### Étape 5 — Rollback (si nécessaire)

⚠️ **Destructif** — supprime toutes les données. Uniquement si la migration a laissé la base dans un état incohérent.

```bash
psql $SUPABASE_DB_URL -f db/rollback/001_jmpartners_v2.2_rollback.sql
```

---

## Notes importantes

**pgvector** : l'index IVFFlat `idx_embeddings_vector` est créé vide et devient actif dès la première insertion. La RPC `match_historique_fec` retourne 0 résultats sur table vide — comportement normal.

**RLS** : activé sur toutes les tables en mode beta (`authenticated USING (true)`). Les agents Python utilisent `SUPABASE_SERVICE_KEY` qui bypasse le RLS automatiquement. Resserrer en production via `responsable_id`.

**Application via Dashboard** : coller `001_jmpartners_v2.2.sql` dans SQL Editor → Run. Le dry run nécessite psql (le Dashboard ne supporte pas ROLLBACK interactif).
