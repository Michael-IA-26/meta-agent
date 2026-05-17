# Composant : langue_francais

## Type
contraintes

## Description
Contrainte de langue : toutes les productions (emails, fiches, rapports, scripts) doivent être rédigées en français standard.
S'applique à l'ensemble des outputs du système de prospection JM Partners.

## Contenu
**Règle principale :**
Toute communication produite par le système — emails de prospection, fiches leads, rapports hebdomadaires, scripts d'appel, synthèses de RDV — doit être rédigée intégralement en français.

**Niveau de langue attendu :**
- Français standard, registre professionnel
- Vouvoiement systématique dans les communications externes
- Éviter les anglicismes inutiles : préférer « courriel » ou « email » à « mail », « rendez-vous » à « meeting », « tableau de bord » à « dashboard »
- Les termes techniques anglais sans équivalent français courant sont tolérés (ex. : CRM, BODACC, SIREN)

**Orthographe et typographie :**
- Respecter les règles typographiques françaises : espace insécable avant « : », « ; », « ! », « ? »
- Majuscule après un point, minuscule après une virgule
- Guillemets français : « … » (pas "…")
- Dates : format JJ/MM/AAAA ou « le [jour] [mois en lettres] [année] »

**Exceptions autorisées :**
- Noms propres de logiciels ou APIs (Pappers, Salesforce, HubSpot)
- Acronymes institutionnels (BODACC, INSEE, SIREN, SIRET, NAF, RCS)
- Termes juridiques sans traduction officielle

**Vérification :**
- Avant tout envoi, relire pour détecter les mots anglais non nécessaires
- Le modèle ne doit jamais produire de réponse dans une autre langue, même si interrogé en anglais dans ce contexte

## Exemples d'utilisation
1. Paramétrer la contrainte de langue dans le system prompt d'un agent de prospection
2. Auditer les outputs d'un modèle pour vérifier l'absence d'anglicismes
3. Former un prestataire externe aux standards rédactionnels de JM Partners

## Ne jamais faire
- Produire un email ou une fiche en anglais, même partiellement
- Utiliser « tu » ou « vous » de façon incohérente dans un même document
- Ignorer les règles typographiques françaises dans un document officiel
