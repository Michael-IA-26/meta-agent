"""Générateur d'emails cold outreach PAS — mode dry_run (sans appel API).

Structure PAS : Problème / Agitation / Solution + CTA + pied RGPD.
Conforme à leadcommercial_cold_email.md (< 120 mots hors signature).
"""

from __future__ import annotations

from typing import Any


_SIGNATURE = """
Cordialement,
Jean-Michel Partenaires
Cabinet JM Partners — Paris 11ème
Tél. : 01 43 00 XX XX | Calendly : calendly.com/jmpartners

---
Si vous ne souhaitez plus être contacté par JM Partners, répondez STOP à ce message. Vos données sont traitées conformément à notre politique de confidentialité.
""".strip()

# ── Templates PAS par secteur ────────────────────────────────────────────────

def _template_restauration_chr(lead: dict, jours: int) -> tuple[str, str]:
    prenom_nom = f"M. {lead['representant']['nom']}"
    denom = lead["denomination"]
    return (
        f"votre comptabilité de démarrage — {denom[:30]}",
        f"""{prenom_nom},

Vous avez créé {denom} il y a {jours} jours. \
Le choix du régime fiscal et votre première déclaration de TVA arrivent dans les prochaines semaines.

Un mauvais choix de régime dès l'ouverture peut générer des redressements coûteux \
et compliquer votre gestion au quotidien pendant des années.

JM Partners accompagne plus de 200 dirigeants TPE en Île-de-France, \
dont de nombreux artisans et restaurateurs. \
Nous intervenons dès le premier mois pour sécuriser vos choix structurants.

Seriez-vous disponible pour un échange de 20 min cette semaine ou la semaine prochaine ?"""
    )


def _template_btp(lead: dict, jours: int) -> tuple[str, str]:
    prenom_nom = f"M. {lead['representant']['nom']}"
    denom = lead["denomination"]
    return (
        f"comptabilité et charges sociales pour votre {lead.get('forme_juridique', 'société')}",
        f"""{prenom_nom},

Vous avez créé {denom} il y a {jours} jours. \
Dans le BTP, la gestion des charges sociales des ouvriers et la facturation \
sous-traitants demandent un suivi rigoureux dès le démarrage.

Un écart déclaratif en début d'activité peut entraîner des pénalités URSSAF \
et bloquer vos appels d'offres publics.

JM Partners accompagne plus de 200 TPE en Île-de-France, \
dont de nombreuses entreprises du bâtiment. \
Un interlocuteur unique suit votre dossier de A à Z.

Seriez-vous disponible pour un échange de 20 min cette semaine ou la semaine prochaine ?"""
    )


def _template_services_tech(lead: dict, jours: int) -> tuple[str, str]:
    prenom_nom = f"M. {lead['representant']['nom']}" if lead['representant'].get('nom') else "Madame, Monsieur"
    # Detect gender if prenom available
    prenom = lead['representant'].get('prenom', '')
    if prenom and prenom[-1].lower() == 'e':
        prenom_nom = f"Mme {lead['representant']['nom']}"
    denom = lead["denomination"]
    return (
        f"optimisation fiscale pour votre activité tech — {denom[:25]}",
        f"""{prenom_nom},

Vous avez créé {denom} il y a {jours} jours. \
Pour une {lead.get('forme_juridique', 'société')} dans les services numériques, \
le choix entre l'IS et l'IR et la valorisation des parts dès le départ ont des impacts durables.

Une structure mal optimisée peut vous faire perdre plusieurs milliers d'euros \
par an et compliquer une future levée de fonds.

JM Partners accompagne plus de 200 dirigeants TPE/PME en Île-de-France, \
y compris dans les secteurs tech et services. \
Nous parlons votre langage.

Seriez-vous disponible pour un échange de 20 min cette semaine ou la semaine prochaine ?"""
    )


def _template_assurance(lead: dict, jours: int) -> tuple[str, str]:
    prenom_nom = f"M. {lead['representant']['nom']}"
    denom = lead["denomination"]
    return (
        f"obligations comptables pour votre agence — {denom[:25]}",
        f"""{prenom_nom},

Vous avez créé {denom} il y a {jours} jours. \
Pour un agent d'assurance en {lead.get('forme_juridique', 'SARL')}, \
les obligations de reporting intermédiaire et la comptabilité des commissions sont complexes dès le premier trimestre.

Un retard de déclaration peut engager votre responsabilité professionnelle \
auprès de votre mandant.

JM Partners accompagne plus de 200 dirigeants TPE en Île-de-France, \
dont des professions réglementées. \
Nous sécurisons votre conformité dès le lancement.

Seriez-vous disponible pour un échange de 20 min cette semaine ou la semaine prochaine ?"""
    )


def _template_generique(lead: dict, jours: int) -> tuple[str, str]:
    prenom_nom = f"M. {lead['representant']['nom']}"
    denom = lead["denomination"]
    fj = lead.get("forme_juridique", "société")
    return (
        f"accompagnement comptable pour votre {fj} — {denom[:25]}",
        f"""{prenom_nom},

Vous avez créé {denom} il y a {jours} jours. \
Les premières semaines sont décisives pour le régime fiscal, \
la TVA et la rémunération du dirigeant.

Un choix structurel mal posé dès le démarrage peut coûter cher \
et demander des années à corriger.

JM Partners accompagne plus de 200 dirigeants TPE/PME en Île-de-France. \
Interlocuteur unique, réactif, nous intervenons dès le premier mois.

Seriez-vous disponible pour un échange de 20 min cette semaine ou la semaine prochaine ?"""
    )


# ── Sélection du template par NAF ────────────────────────────────────────────

def _pick_template(lead: dict, jours: int) -> tuple[str, str]:
    naf = lead.get("code_naf", "")
    p2 = naf[:2]
    p4 = naf[:4].replace(".", "")

    if p4 == "1071" or p2 == "56":
        return _template_restauration_chr(lead, jours)
    if p2 in {"41", "42", "43"}:
        return _template_btp(lead, jours)
    if p2 in {"62", "63", "70", "71", "72", "73", "74"}:
        return _template_services_tech(lead, jours)
    if p2 in {"65", "66", "67"}:
        return _template_assurance(lead, jours)
    return _template_generique(lead, jours)


# ── API publique ──────────────────────────────────────────────────────────────

def generate_cold_email(lead: dict[str, Any], jours_depuis_creation: int) -> dict[str, Any]:
    """Génère un email cold outreach PAS pour un lead qualifié (CHAUD ou TIÈDE).

    Args:
        lead:                    Dictionnaire lead évalué.
        jours_depuis_creation:   Nombre de jours depuis la création (pour personnalisation).

    Returns:
        Dictionnaire avec : objet, corps, signature, email_complet, word_count.
    """
    objet, corps = _pick_template(lead, jours_depuis_creation)

    email_complet = f"Objet : {objet}\n\n{corps}\n\n{_SIGNATURE}"

    word_count = len(corps.split())

    return {
        "objet": objet,
        "corps": corps,
        "signature": _SIGNATURE,
        "email_complet": email_complet,
        "word_count": word_count,
        "conforme_120_mots": word_count <= 120,
    }


def generate_fiche_lead(result: dict[str, Any], email: dict[str, Any]) -> str:
    """Génère la fiche lead au format Markdown (format_fiche_lead.md)."""
    r = result
    rep = r.get("representant", {})
    details = "\n".join(f"  - {d}" for d in r.get("scoring_details", []))
    date_detection = "02/06/2026"  # date d'exécution du dry_run

    return f"""## Fiche Lead — {r['denomination']}

### Identification
- SIREN           : {r.get('siren', 'SIMUL')}
- Raison sociale  : {r['denomination']}
- Forme juridique : {r.get('forme_juridique', '?')}
- Code NAF        : {r.get('code_naf', '?')} — {r.get('libelle_naf', '?')}
- Adresse siège   : {r['code_postal']}
- Date création   : {r.get('date_creation', '?')}
- Effectif déclaré: cf. données source

### Dirigeant
- Nom / Prénom    : {rep.get('nom', '?')} {rep.get('prenom', '?')}
- Qualité         : Gérant / Président
- Email pro       : non disponible (dry_run)
- Téléphone       : non disponible (dry_run)

### Scoring ICP
- Score total     : {r['score']}/100
- Statut          : {r['statut']}
- Détail scoring  :
{details}

### Signal(s) déclencheur(s)
- Type            : création d'entreprise (signal principal)
- Date détection  : {date_detection}
- Source          : Simulation dry_run (J1)
- Référence       : {r.get('id', '?')}

### Email cold outreach
- Objet           : {email['objet']}
- Nombre de mots  : {email['word_count']} (≤ 120 mots : {'✅' if email['conforme_120_mots'] else '❌'})

### Suivi prospection
- Statut          : nouveau
- Date 1er contact: à planifier
- Canal           : email
- Prochaine action: Envoi email J+0, relance J+7
- Notes           : Lead généré en dry_run Jour 1 — validation pipeline
"""
