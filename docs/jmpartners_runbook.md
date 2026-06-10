# JM Partners — Runbook de mise en production

> Référence opérationnelle pour déployer, surveiller et diagnostiquer le service JM Partners sur Railway.
> Mis à jour le 2026-06-11. Tests : **73 passed, 2 xfailed** (0 failed).

---

## 1. Variables d'environnement requises (Doppler)

Toutes ces variables doivent être présentes dans le projet Doppler **jmpartners / production** avant le premier déploiement.

### 1.1 Supabase

| Variable | Exemple | Rôle |
|----------|---------|------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` | URL de l'instance Supabase |
| `SUPABASE_SERVICE_KEY` | `eyJhbGciOiJIUzI1...` | Clé service-role (pas la clé anon) |

> La clé **service-role** est nécessaire pour contourner les RLS. Ne jamais utiliser la clé anon en prod.

---

### 1.2 SMTP (envoi d'emails)

| Variable | Exemple | Rôle |
|----------|---------|------|
| `SMTP_HOST` | `smtp.gmail.com` | Serveur SMTP |
| `SMTP_PORT` | `587` | Port TLS (587 = STARTTLS, 465 = SSL) |
| `SMTP_USER` | `contact@jmpartners.fr` | Adresse expéditeur |
| `SMTP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Mot de passe applicatif Gmail (pas le mot de passe compte) |

> Pour Gmail : activer la validation en 2 étapes puis générer un **mot de passe d'application** dans Sécurité du compte. Ne pas utiliser le mot de passe du compte Google.

---

### 1.3 IMAP (lecture des emails entrants)

| Variable | Exemple | Rôle |
|----------|---------|------|
| `IMAP_HOST` | `imap.gmail.com` | Serveur IMAP SSL |
| `IMAP_USER` | `contact@jmpartners.fr` | Même adresse que SMTP_USER |
| `IMAP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Même mot de passe applicatif que SMTP |
| `IMAP_POLL_MINUTES` | `15` | Intervalle de polling en minutes (défaut : 15) |

> Si `IMAP_HOST` est absent, le mail_handler retourne immédiatement sans erreur — le service continue de fonctionner sans lecture d'emails.

---

### 1.4 Anthropic (génération d'emails Claude)

| Variable | Exemple | Rôle |
|----------|---------|------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` | Clé API Anthropic pour Claude Haiku |

> Utilisé par `mail_handler` (classification) et `relance_handler` (rédaction). Si absent : fallback statique automatique, les deux agents continuent de fonctionner.

---

### 1.5 Telegram (alertes et notifications)

| Variable | Exemple | Rôle |
|----------|---------|------|
| `TELEGRAM_BOT_TOKEN` | `123456789:AAH...` | Token du bot Telegram (@BotFather) |
| `TELEGRAM_CHAT_ID` | `-1001234567890` | ID du canal ou groupe cible |

> Si absent : les agents fonctionnent normalement, les alertes Telegram sont silencieusement ignorées. Configurer via `@BotFather` sur Telegram puis récupérer l'ID du chat avec `https://api.telegram.org/bot<TOKEN>/getUpdates`.

---

### 1.6 Rapports par email

| Variable | Exemple | Rôle |
|----------|---------|------|
| `RAPPORT_EMAIL` | `michael@jmpartners.fr` | Destinataire des rapports quotidiens (écheances, alertes) |
| `RAPPORT_DESTINATAIRE` | `michael@jmpartners.fr` | Alias utilisé par echeance_agent (même valeur) |

---

### 1.7 Cabinet et scheduler

| Variable | Exemple | Rôle |
|----------|---------|------|
| `CABINET_ID` | `jmpartners` | Identifiant du cabinet (filtre Supabase) |
| `SCHEDULER_ENABLED` | `true` | `false` pour désactiver le cron (défaut : `true`) |
| `CRON_SCHEDULE` | `0 7 * * 1-5` | Expression cron du cycle principal (défaut : 07h00 lun-ven, timezone Europe/Paris) |

> Format cron : `minute heure jour mois jour_semaine`. Exemples : `0 8 * * 1-5` = 08h00 lun-ven, `0 7 * * *` = 07h00 tous les jours.

---

### Checklist complète Doppler

```
SUPABASE_URL              ✓
SUPABASE_SERVICE_KEY      ✓
SMTP_HOST                 ✓
SMTP_PORT                 ✓
SMTP_USER                 ✓
SMTP_PASSWORD             ✓
IMAP_HOST                 ✓
IMAP_USER                 ✓
IMAP_PASSWORD             ✓
IMAP_POLL_MINUTES         ✓  (défaut 15)
ANTHROPIC_API_KEY         ✓
TELEGRAM_BOT_TOKEN        ✓
TELEGRAM_CHAT_ID          ✓
RAPPORT_EMAIL             ✓
RAPPORT_DESTINATAIRE      ✓
CABINET_ID                ✓
SCHEDULER_ENABLED         ✓  (défaut true)
CRON_SCHEDULE             ✓  (défaut "0 7 * * 1-5")
```

---

## 2. Vérifier que le service tourne

### 2.1 Logs Railway

Dans le dashboard Railway → service **jmpartners** → onglet **Logs**, chercher :

```
# Démarrage normal
INFO apps.jmpartners.main — Scheduler JM Partners démarré — cron principal : 0 7 * * 1-5
INFO apps.jmpartners.main — IMAP poll démarré en arrière-plan (15 min)

# Cycle qui tourne
INFO apps.jmpartners.orchestrator — Orchestrateur JM Partners — démarrage (dry_run=False)
INFO apps.jmpartners.orchestrator — Orchestrateur JM Partners — cycle terminé

# Emails traités
INFO apps.jmpartners.agents.mail_handler — mail_handler : 3 emails non lus
INFO apps.jmpartners.agents.mail_handler — mail_handler terminé : 3 traités, 0 non matchés
```

Lignes à surveiller :
- `ERROR` → agent en erreur (voir section 3)
- `WARNING mail_handler — IMAP non configuré` → variables IMAP manquantes
- `WARNING relance_handler — Anthropic non disponible` → clé API Anthropic manquante (fallback actif)

---

### 2.2 Endpoint GET /health

```bash
curl https://<votre-service>.railway.app/health
```

Réponse attendue :

```json
{
  "statut": "ok",
  "agents": {
    "mail_handler": "ok",
    "tva_agent": "ok",
    "echeance_agent": "ok",
    "cloture_handler": "ok",
    "acompte_is_agent": "ok",
    "bilan_agent": "ok",
    "declaration_is_agent": "ok",
    "document_checker": "ok",
    "relance_handler": "ok",
    "notification_agent": "ok"
  },
  "dernier_run": {
    "timestamp": "2026-06-11T07:00:12.345Z",
    "duree_secondes": 42.3,
    "agents_ok": 7,
    "agents_ko": 0,
    "erreurs": []
  }
}
```

Si `dernier_run` est `null` : soit Supabase n'est pas configuré, soit aucun cycle n'a encore tourné.

Si `agents_ko > 0` : consulter `dernier_run.erreurs` pour identifier l'agent en défaut.

---

### 2.3 Table `journaux` Supabase

Dans Supabase Studio → Table Editor → `journaux`, filtrer par `type_action = 'orchestrator_run'` :

```sql
SELECT created_at, statut, contenu, metadata
FROM journaux
WHERE type_action = 'orchestrator_run'
ORDER BY created_at DESC
LIMIT 10;
```

Un run normal ressemble à :

```
created_at   : 2026-06-11 07:00:12+00
statut       : ok
contenu      : 7 agents OK, 0 KO, durée 42.3s
metadata     : {"duree_secondes": 42.3, "agents_ok": 7, "agents_ko": 0, "erreurs": []}
```

Pour voir les dernières relances envoyées :

```sql
SELECT created_at, contact_id, contenu, statut
FROM journaux
WHERE type_action = 'relance_envoyee'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 3. Que faire si un agent est KO

### 3.1 Identifier l'agent en erreur

**Via logs Railway** (chercher `ERROR apps.jmpartners.orchestrator`) :
```
ERROR apps.jmpartners.orchestrator — erreur tva_agent : Connection timeout
ERROR apps.jmpartners.orchestrator — erreur relance_handler : SMTP error
```

**Via /health** :
```json
"dernier_run": {
  "agents_ko": 1,
  "erreurs": ["tva_agent: Connection timeout after 30s"]
}
```

**Via journaux Supabase** :
```sql
SELECT created_at, metadata->>'erreurs' AS erreurs
FROM journaux
WHERE type_action = 'orchestrator_run' AND statut = 'erreur'
ORDER BY created_at DESC LIMIT 5;
```

---

### 3.2 Diagnostics par agent

#### `mail_handler` — `IMAP non configuré`
```
WARNING apps.jmpartners.agents.mail_handler — IMAP non configuré (IMAP_HOST/IMAP_USER/IMAP_PASSWORD manquants)
```
→ Vérifier les 3 variables IMAP dans Doppler. Redéployer après correction.

#### `mail_handler` — `Erreur IMAP`
```
ERROR apps.jmpartners.agents.mail_handler — Erreur IMAP : [Errno 111] Connection refused
```
→ IMAP_HOST incorrect ou port bloqué. Tester : `openssl s_client -connect imap.gmail.com:993`.

#### `tva_agent` / `echeance_agent` — `Supabase timeout`
```
ERROR apps.jmpartners.agents.tva_agent — Erreur fetch déclarations TVA : Connection timeout
```
→ Supabase indisponible (vérifier status.supabase.com). Réessayera au prochain cycle.

#### `relance_handler` — `Erreur SMTP`
```
ERROR apps.jmpartners.agents.relance_handler — Erreur SMTP vers contact@dupont.fr : [Errno 535] Authentication failed
```
→ Mot de passe SMTP expiré. Régénérer un mot de passe d'application Gmail et mettre à jour SMTP_PASSWORD dans Doppler.

#### `relance_handler` — `Anthropic non disponible`
```
WARNING apps.jmpartners.agents.relance_handler — Anthropic non disponible, fallback statique : ANTHROPIC_API_KEY est requis
```
→ Non bloquant : le fallback statique compose l'email. Vérifier ANTHROPIC_API_KEY dans Doppler.

#### `bilan_agent` / `acompte_is_agent` / `declaration_is_agent` — erreur email
```
ERROR apps.jmpartners.agents.bilan_agent — Erreur envoi email bilan : ...
```
→ Vérifier SMTP_PASSWORD. Ces agents n'ont pas de fallback email (contrairement à relance_handler).

---

### 3.3 Forcer un nouveau cycle après correction

Les agents crashés ne bloquent pas les autres. Après correction de la variable Doppler :

1. Dans Railway : **Redeploy** (le nouveau déploiement récupère les variables Doppler actualisées)
2. Le prochain cycle cron relancera automatiquement tous les agents
3. Pour forcer immédiatement : voir section 4

---

## 4. Lancer un run manuel

### 4.1 Via le dashboard — dry-run (sans effet de bord)

```
POST https://<votre-service>.railway.app/api/dry-run
```

```bash
curl -X POST https://<votre-service>.railway.app/api/dry-run | jq .
```

Simule le cycle complet sans envoyer d'emails ni écrire en base. Utile pour vérifier la configuration.

---

### 4.2 Via Railway CLI — cycle complet

Dans Railway, ouvrir un shell sur le service jmpartners :

```bash
# Cycle complet (prod)
python -m apps.jmpartners.main --once

# Cycle complet sans effet de bord
python -m apps.jmpartners.main --once --dry-run

# Vérifier un dossier spécifique
python -m apps.jmpartners.main --check-dossier <UUID_DOSSIER>

# Rapport échéances uniquement
python -m apps.jmpartners.main --echeances

# Surveillance TVA uniquement
python -m apps.jmpartners.main --tva
```

---

### 4.3 Relancer un dossier depuis le dashboard web

```
POST https://<votre-service>.railway.app/api/relancer/<UUID_DOSSIER>
```

```bash
curl -X POST https://<votre-service>.railway.app/api/relancer/d001 | jq .
```

Déclenche `document_checker` + `relance_handler` pour ce dossier précis.

---

### 4.4 Désactiver temporairement le scheduler

Dans Doppler : `SCHEDULER_ENABLED = false` → Redeploy.

Le service reste actif (le dashboard `/health` répond, l'IMAP poll continue), seul le cron principal est suspendu.

---

## 5. Résumé des tests (2026-06-11)

```
pytest tests/jmpartners/ -v
================================== test session ===================================
73 passed, 2 xfailed in 0.98s

Fichier                          Tests   Statut
─────────────────────────────────────────────────────────────────────────────
test_document_checker.py            10   ✅ 10/10
test_echeance_agent.py              14   ✅ 14/14
test_mail_handler.py                 8   ✅  8/8
test_orchestrator.py            12 + 2xf ✅ 12/12 + 2 xfail Sprint 3
test_prod_features.py               20   ✅ 20/20
test_relance_handler.py              9   ✅  9/9
─────────────────────────────────────────────────────────────────────────────
TOTAL                               75   73 passed, 2 xfailed, 0 failed

xfail attendus (Sprint 3 non implémenté) :
  - test_email_document_manquant_declenche_relance
  - test_notification_agent_appele_pour_alertes_urgentes
```

---

## 6. Contacts et ressources

| Ressource | URL |
|-----------|-----|
| Railway dashboard | https://railway.app/project/<ID> |
| Supabase Studio | https://app.supabase.com/project/<ID> |
| Doppler secrets | https://dashboard.doppler.com/workplace/<ID>/projects/jmpartners |
| Status Supabase | https://status.supabase.com |
| Status Anthropic | https://status.anthropic.com |
