# ADR-002 — Conformité RGPD et Zero Data Retention

| Champ | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-05-10 |
| **Auteurs** | Michael, Jeffrey |
| **Contexte** | Sprint 2 — LeadCommercial + Agent Email |

---

## Contexte

LeadCommercial traite des données personnelles de dirigeants d'entreprises
(nom, prénom, email, téléphone) collectées via API Sirene INSEE, RNE INPI
et signaux d'intention (Reddit, forums).

L'agent email analyse des emails professionnels contenant potentiellement
des données personnelles et confidentielles (clients, prospects, partenaires).

Avant tout test sur la boîte JM Partners (cabinet d'expertise comptable,
soumis au secret professionnel), la conformité RGPD doit être documentée
et validée.

---

## Décisions

### 1. Zero Data Retention (ZDR) sur l'API Anthropic

**Décision** : activer l'option Zero Data Retention sur le compte Anthropic.

**Pourquoi** : sans ZDR, Anthropic peut conserver les prompts et réponses
jusqu'à 30 jours à des fins d'amélioration du modèle. Avec ZDR, aucune
donnée n'est conservée après la réponse.

**Action** : contacter support@anthropic.com pour activer ZDR sur le compte.
Variable d'environnement : `ANTHROPIC_ZDR_ENABLED=true` (documentaire,
pas technique — ZDR est activé au niveau du compte).

### 2. Variable GDPR_MODE

**Décision** : introduire une variable `GDPR_MODE` dans Doppler.

**Comportement selon valeur** :

| Valeur | Comportement |
|---|---|
| `strict` | Aucune donnée personnelle dans les logs. Pseudonymisation des emails analysés. Pas de stockage des corps d'emails. |
| `standard` | Logs normaux. Stockage Supabase standard. Usage interne uniquement. |

**Valeur par défaut** : `standard` pour les tests internes.
**Valeur pour JM Partners** : `strict` dès le premier test réel.

### 3. Données collectées par LeadCommercial

**Base légale** : intérêt légitime (prospection B2B, Art. 6.1.f RGPD).
Les données collectées sont publiques (Registre du Commerce, BODACC).

**Données traitées** :
- Nom, prénom du dirigeant (source : RNE INPI — données publiques)
- Email professionnel (enrichissement Dropcontact — RGPD-first)
- Téléphone professionnel (enrichissement optionnel)
- Données entreprise : SIREN, NAF, adresse (données publiques)

**Durée de conservation** :
- Leads actifs : durée du contrat client + 1 an
- Leads optout : suppression email/tel immédiate, conservation SIREN 3 ans (traçabilité)
- Leads perdus : anonymisation après 2 ans

### 4. Droit d'opt-out

**Décision** : tout prospect peut demander la suppression de ses données.

**Implémentation** :
- Statut lead → `optout` dans Supabase
- Suppression immédiate : `dirigeant_email`, `dirigeant_tel`
- Conservation : SIREN + `optout_at` (preuve de conformité)
- Jamais recontacté : vérification systématique avant tout envoi

### 5. Mentions légales dans les cold emails

**Décision** : tout email envoyé par LeadCommercial inclut :
- Identification de l'expéditeur (JM Partners)
- Motif du contact (création d'entreprise détectée)
- Lien de désinscription fonctionnel
- Mention RGPD : "Vous pouvez exercer vos droits à l'adresse : [email]"

---

## Conséquences

### Ce qui change immédiatement

- `GDPR_MODE=standard` ajouté dans Doppler (environnement dev)
- `GDPR_MODE=strict` à configurer avant tout test JM Partners
- ADR-002 communiqué à Jeffrey avant tout accès aux données clients

### Ce qui est bloquant

- **Tests sur boîte JM Partners** : bloqués jusqu'à confirmation ZDR activé
- **Envoi cold emails réels** : bloqué jusqu'à validation mentions légales par JM Partners
- **Stockage emails analysés** : en `GDPR_MODE=strict`, seul le résumé est stocké (pas le corps)

### Variables Doppler à ajouter
---

## Références

- RGPD Art. 6.1.f — Base légale intérêt légitime
- RGPD Art. 17 — Droit à l'effacement
- RGPD Art. 21 — Droit d'opposition (prospection commerciale)
- Anthropic Zero Data Retention : https://privacy.anthropic.com
- Dropcontact conformité RGPD : https://www.dropcontact.com/rgpd
