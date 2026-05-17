# Rapport qualité — 50 leads IDF simulés — JM Partners

**Date** : 2026-05-17
**Source** : Données simulées (représentatives du flux Sirene IDF)
**Périmètre** : Entreprises IDF créées entre 2025-11-17 et 2026-05-17
**Critères ICP** : TPE/PME IDF (0-49 sal.), non cessée, hors procédure collective, hors secteurs exclus

> ⚠️ **Données simulées** : Ce rapport repose sur 50 entreprises fictives construites pour être représentatives de la réalité du registre Sirene IDF (distribution sectorielle, formes juridiques, effectifs, localisation). Il vise à valider la logique de filtrage ICP avant la mise en production.
>
> **Test sur données réelles prévu en S4** — intégration API INSEE Sirene (gratuite, sans limite, OAuth2) planifiée pour remplacer ce simulateur. Voir [docs/leadcommercial/sirene-pappers-champs-utiles.md](./sirene-pappers-champs-utiles.md) § 6.

---

## 1. Résumé exécutif

| Indicateur | Valeur |
|---|---|
| Leads simulés | 50 |
| Leads qualifiés ICP | **38** |
| Leads exclus | 12 |
| Taux de passage ICP | **76,0 %** |

### Motifs d'exclusion

| Motif | Nb | % des exclusions |
|---|---|---|
| Effectif > 49 salariés | 6 | 50 % |
| Procédure collective en cours | 3 | 25 % |
| Secteur exclu | 2 | 17 % |
| Entreprise cessée | 1 | 8 % |

### Répartition des leads qualifiés par département

| Département | Nb qualifiés | % des qualifiés |
|---|---|---|
| 75 — Paris | 14 | 37 % |
| 77 — Seine-et-Marne | 4 | 11 % |
| 78 — Yvelines | 4 | 11 % |
| 91 — Essonne | 4 | 11 % |
| 92 — Hauts-de-Seine | 5 | 13 % |
| 93 — Seine-Saint-Denis | 3 | 8 % |
| 94 — Val-de-Marne | 2 | 5 % |
| 95 — Val-d'Oise | 2 | 5 % |

---

## 2. Leads qualifiés ICP (38)

| # | SIREN | Dénomination | Dept | Ville | NAF | Forme | Création | Effectif | Dirigeant |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 934 521 087 | DIGITECH SOLUTIONS | 75 | Paris 11e | 62.01Z | SASU | 2025-12-15 | 0 sal. | Thomas Lefebvre |
| 2 | 921 874 563 | LE COMPTOIR DE BASTILLE | 75 | Paris 4e | 56.10A | SARL | 2026-01-08 | 2 sal. | Marie Chen |
| 3 | 918 236 741 | ARTISAN PLOMBERIE PARIS | 75 | Paris 15e | 43.22B | EURL | 2025-12-01 | 1 sal. | François Dubois |
| 4 | 943 102 856 | INVEST PATRIMOINE 75 | 75 | Paris 8e | 64.20Z | SASU | 2026-02-14 | 0 sal. | Laurent Moreau |
| 5 | 928 763 412 | CABINET WELLNESS | 75 | Paris 17e | 86.21Z | SELARL | 2025-11-25 | 1 sal. | Aïcha Diallo |
| 6 | 951 430 278 | STARTUP MOBILITY | 75 | Paris 10e | 71.12B | SAS | 2026-03-10 | 3 sal. | Kevin Nguyen |
| 7 | 912 087 634 | MEDIA CONTENT 75 | 75 | Paris 3e | 73.11Z | SASU | 2026-01-22 | 0 sal. | Sarah Lecompte |
| 8 | 937 651 024 | BOULANGERIE DU MARAIS | 75 | Paris 4e | 56.10C | SARL | 2025-12-20 | 4 sal. | Jean-Pierre Faure |
| 9 | 924 308 175 | CONSEIL RH INDÉPENDANT | 75 | Paris 9e | 70.22Z | EURL | 2026-02-05 | 0 sal. | Christine Vidal |
| 10 | 948 217 360 | SMART IMMO PARIS | 75 | Paris 16e | 68.10Z | SAS | 2025-11-30 | 2 sal. | Philippe Rousseau |
| 11 | 931 584 702 | TRANSPORT VTC SEINE | 75 | Paris 19e | 49.32Z | SASU | 2026-01-15 | 1 sal. | Mourad Benali |
| 12 | 916 743 089 | ARCHITECTURE & DESIGN | 75 | Paris 6e | 71.11Z | SAS | 2026-03-22 | 2 sal. | Isabelle Fontaine |
| 13 | 942 830 561 | E-COMMERCE LIFESTYLE | 75 | Paris 20e | 47.91B | SASU | 2025-12-10 | 0 sal. | Antoine Garnier |
| 14 | 957 412 836 | FORMATION PRO DIGITAL | 75 | Paris 13e | 85.59B | SARL | 2026-04-01 | 3 sal. | Nadia Amara |
| 15 | 923 670 415 | MENUISERIE SEINE-ET-MARNE | 77 | Melun | 43.32A | EURL | 2025-12-05 | 2 sal. | Christophe Simon |
| 16 | 946 183 527 | AGRI CONSEIL 77 | 77 | Meaux | 74.90B | SAS | 2026-01-18 | 0 sal. | Paul Lemaire |
| 17 | 918 054 263 | RESTO RAPIDE PROVINS | 77 | Provins | 56.10B | SARL | 2026-03-15 | 5 sal. | Ahmed Mansouri |
| 18 | 934 726 018 | BTP RÉNOVATION 77 | 77 | Pontault-Combault | 41.20A | SASU | 2025-11-20 | 3 sal. | Stéphane Girard |
| 19 | 947 231 685 | YVELINES CONSULTING | 78 | Versailles | 70.22Z | SASU | 2026-02-10 | 0 sal. | Élodie Martin |
| 20 | 921 508 347 | MAINTENANCE INDUS. 78 | 78 | Rambouillet | 33.20C | EURL | 2025-12-18 | 4 sal. | Patrick Renard |
| 21 | 938 064 712 | NUTRITION CONSEIL | 78 | Saint-Germain-en-Laye | 86.90F | SELARL | 2026-03-25 | 1 sal. | Sophie Marchand |
| 22 | 912 847 530 | SCI LES CHÊNES | 78 | Versailles | 68.10Z | SCI | 2026-01-30 | 0 sal. | Henri Duval |
| 23 | 953 017 486 | ESSONNE SERVICES | 91 | Évry-Courcouronnes | 81.10Z | SAS | 2025-12-08 | 8 sal. | Fatou Diop |
| 24 | 927 634 851 | SOLAR INSTALL ESSONNE | 91 | Corbeil-Essonnes | 43.21B | SASU | 2026-02-20 | 2 sal. | Romain Leblanc |
| 25 | 941 285 073 | TAXI AÉROPORT ORLY | 91 | Athis-Mons | 49.32Z | EURL | 2025-11-22 | 1 sal. | Oumar Sy |
| 26 | 916 430 258 | AUTO ÉCOLE MODERNE | 91 | Massy | 85.53Z | SARL | 2026-04-12 | 6 sal. | Virginie Lepage |
| 27 | 948 765 302 | HAUTS-DE-SEINE AUDIT | 92 | Boulogne-Billancourt | 69.20Z | SAS | 2025-12-22 | 3 sal. | Charles Arnaud |
| 28 | 922 183 047 | NEUILLY COACHING | 92 | Neuilly-sur-Seine | 85.59B | SASU | 2026-01-10 | 0 sal. | Valérie Dumont |
| 29 | 935 047 612 | BTP ISSY-LES-MOULINEAUX | 92 | Issy-les-Moulineaux | 43.91A | EURL | 2026-03-05 | 5 sal. | Bruno Picard |
| 30 | 914 526 780 | COMMERCE COURBEVOIE | 92 | Courbevoie | 47.29Z | SARL | 2025-11-28 | 3 sal. | Lin Wei |
| 31 | 957 830 146 | SÉCURITÉ PRIVÉE 92 | 92 | Nanterre | 80.10Z | SAS | 2026-02-14 | 12 sal. | Marc Tissot |
| 32 | 929 471 053 | TRAITEUR SAINT-OUEN | 93 | Saint-Ouen | 56.21Z | SARL | 2026-01-25 | 4 sal. | Karim Belkacem |
| 33 | 943 618 207 | PHOTO & VIDÉO 93 | 93 | Montreuil | 74.20Z | SASU | 2025-12-15 | 0 sal. | Julia Bonnet |
| 34 | 918 372 564 | PRESSING SAINT-DENIS | 93 | Saint-Denis | 96.01Z | SARL | 2026-03-18 | 3 sal. | Pham Thi Lan |
| 35 | 951 064 738 | VAL-DE-MARNE JARDINS | 94 | Créteil | 81.30Z | EURL | 2026-02-08 | 2 sal. | Serge Morin |
| 36 | 924 817 360 | IMMOBILIER VINCENNES | 94 | Vincennes | 68.10Z | SAS | 2026-01-20 | 1 sal. | Claire Germain |
| 37 | 937 250 481 | MEDIA NUMÉRIQUE 95 | 95 | Cergy | 73.20Z | SASU | 2025-12-28 | 0 sal. | Théo Jacquot |
| 38 | 912 584 073 | SCI PONTOISE INVEST | 95 | Pontoise | 68.10Z | SCI | 2026-02-22 | 0 sal. | Brigitte Aumont |

---

## 3. Leads exclus (12)

| # | SIREN | Dénomination | Dept | Ville | NAF | Création | Motif d'exclusion |
|---|---|---|---|---|---|---|---|
| 1 | 852 317 409 | LOGISTIQUE IDF EXPRESS | 94 | Vitry-sur-Seine | 52.29B | 2026-01-05 | Effectif hors ICP — 120 salariés (tranche 22) |
| 2 | 876 204 531 | INTERIM SOLUTIONS 75 | 75 | Paris 2e | 78.20Z | 2025-12-02 | Effectif hors ICP — 85 salariés (tranche 21) |
| 3 | 891 473 620 | NETTOYAGE INDUSTRIEL IDF | 93 | Aubervilliers | 81.21Z | 2026-02-25 | Effectif hors ICP — 67 salariés (tranche 21) |
| 4 | 864 590 217 | TECH SCALE-UP PARIS | 75 | Paris 18e | 62.01Z | 2026-03-01 | Effectif hors ICP — 55 salariés (tranche 21) |
| 5 | 843 726 105 | HOLDING PATRIMONIALE 75 | 75 | Paris 16e | 64.20Z | 2025-11-20 | Effectif hors ICP — 250 salariés (tranche 32) |
| 6 | 871 034 596 | AUTO ÉCOLE NUMÉRIQUE | 78 | Versailles | 85.53Z | 2026-04-05 | Effectif hors ICP — 62 salariés (tranche 21) |
| 7 | 934 082 716 | RESTAURANT LE SOLEIL | 91 | Juvisy-sur-Orge | 56.10A | 2025-11-15 | Procédure collective en cours |
| 8 | 918 645 302 | BTP CONSTRUCT 77 | 77 | Chelles | 41.20A | 2025-12-10 | Procédure collective en cours |
| 9 | 942 307 185 | COMMERCE DÉTAIL PARIS | 75 | Paris 5e | 47.19B | 2026-01-08 | Procédure collective en cours |
| 10 | 887 541 263 | ASSOC. CULTURELLE MONTMARTRE | 75 | Paris 18e | 94.99Z | 2026-02-15 | Secteur exclu — NAF 94.99Z (association loi 1901) |
| 11 | 903 218 457 | GRANDE SURFACE SEINE-NORD | 93 | Aulnay-sous-Bois | 47.11B | 2026-01-20 | Secteur exclu — NAF 47.11B (grande surface) |
| 12 | 929 870 341 | SERVICES RAPIDES 94 | 94 | Ivry-sur-Seine | 74.90B | 2025-12-05 | Entreprise cessée |

---

## 4. Méthodologie de simulation

**Objectif** : Valider la logique de filtrage ICP JM Partners avant connexion à une source de données réelle.

**Construction des 50 leads simulés :**
- Distribution géographique calquée sur le flux Sirene IDF 2024-2025 : surreprésentation de Paris (38 %), proportionnelle aux autres départements.
- Formes juridiques : SASU (40 %), SARL (24 %), SAS (18 %), EURL (12 %), SCI / SELARL (6 %) — distribution représentative des créations récentes en IDF.
- Secteurs : services B2B (30 %), BTP/artisanat (20 %), commerce/restauration (20 %), immobilier (10 %), tech/numérique (12 %), santé libérale (8 %).
- Effectifs : 72 % des leads ont 0-5 salariés ; 12 % intentionnellement hors ICP (> 49 sal.) pour tester le filtre.
- Cas d'exclusion intentionnels : 3 procédures collectives (6 %), 2 secteurs exclus (4 %), 1 cessée (2 %).

**Critères ICP appliqués (dans l'ordre) :**

1. Entreprise non cessée (`entreprise_cessee = false`)
2. Siège social en Île-de-France (dept 75, 77, 78, 91, 92, 93, 94, 95)
3. Aucune procédure collective en cours
4. Effectif ≤ 49 salariés — priorité à `effectif_min` numérique, fallback `tranche_effectif` normalisée (zfill 2)
5. Secteur hors exclusions (associations NAF 94.xx, grandes surfaces 47.11A/B, enseignement public 85.xx)

**Limites de cette simulation :**
- Les SIRENs sont fictifs et ne correspondent pas à des entreprises réelles.
- La distribution des motifs d'exclusion est délibérément représentative, pas aléatoire.
- Le signal « changement de dirigeant » (BODACC) n'est pas simulé (prévu S3).
- Aucun rapprochement CRM ni déduplication n'est effectué.

---

## 5. Prochaines étapes

| Action | Sprint | Responsable |
|---|---|---|
| Intégration API INSEE Sirene (OAuth2, gratuite, sans limite) | S4 | Mika |
| Remplacement de ce simulateur par un vrai flux Sirene | S4 | Mika |
| Test sur 500 leads réels pour valider la distribution des exclusions | S4 | Jeffrey |
| Ajout du signal changement de dirigeant (BODACC) | S3 | Mika |
| Activation du filtre `effectif_min` via API Pappers (plan payant) | S4 | Jeffrey |

---

*Rapport généré le 2026-05-17 — JM Partners / Signal Agent v0.1 — données simulées*
