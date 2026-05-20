# Composant : signal_creation_entreprise

## Type
signal

## Description
Signal de création récente d'entreprise (moins de 6 mois) détecté via les registres publics.
Indique une forte probabilité de besoin comptable non encore satisfait par un cabinet établi.

## Contenu
**Définition du signal :**
Une entreprise est considérée « création récente » si sa date d'immatriculation au RCS est postérieure à J-180 (6 mois glissants à la date d'analyse).

**Sources de détection :**
- API Pappers (champ `date_immatriculation`)
- API INSEE SIRENE (champ `dateCreationEtablissement`)
- BODACC série A (annonces de constitution de société)

**Critères de qualification du signal :**
- Date d'immatriculation ≤ 6 mois
- Forme juridique éligible : SAS, SARL, EURL, SASU, SCI (hors auto-entrepreneur si CA < seuil)
- Siège social en Île-de-France (codes postaux 75, 77, 78, 91, 92, 93, 94, 95)
- Effectif déclaré : 0 à 50 salariés
- Code NAF hors secteurs exclus (voir `exclusions_leads.md`)

**Niveau de priorité :** HAUTE — fenêtre d'opportunité maximale entre M+1 et M+5 après création

**Données à extraire pour la fiche lead :**
- SIREN, raison sociale, forme juridique
- Date d'immatriculation exacte
- Nom du dirigeant (gérant ou président)
- Adresse du siège
- Code NAF + libellé activité
- Capital social déclaré

## Exemples d'utilisation
1. Alimenter la file de prospection hebdomadaire avec les entreprises créées dans les 30 derniers jours
2. Déclencher l'envoi d'un email de prospection ciblé « nouveau dirigeant »
3. Calculer le score ICP en combinaison avec d'autres signaux (voir `scoring_icp_jm.md`)

## Ne jamais faire
- Contacter une entreprise dont la date de création dépasse 6 mois via ce signal seul
- Ignorer la vérification de la forme juridique avant de scorer le lead
- Confondre date d'immatriculation et date de début d'activité déclarée
