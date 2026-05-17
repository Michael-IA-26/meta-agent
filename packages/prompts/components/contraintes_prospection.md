# Composant : contraintes_prospection

## Type
contraintes

## Description
Règles opérationnelles de prospection B2B par email pour JM Partners.
Encadre la fréquence, le timing, la gestion des opt-outs et les bonnes pratiques d'envoi.

## Contenu
**Fréquence d'envoi :**
- Maximum 2 emails par prospect sur une séquence de 30 jours
- J+0 : premier contact (signal frais)
- J+7 pour les leads chauds (score ≥ 75), J+14 pour les leads tièdes (score 50-74)
- Pause obligatoire de 60 jours minimum après 2 emails sans réponse

**Timing d'envoi optimal :**
- Mardi au jeudi : 9h00-10h30 ou 14h00-15h30
- Éviter : lundi matin, vendredi après-midi, jours fériés, première semaine d'août
- Fuseau horaire : Europe/Paris

**Gestion des opt-outs :**
- Tout email doit contenir un lien de désinscription ou la mention « Répondez STOP pour ne plus être contacté »
- Traitement des opt-outs sous 72h maximum
- Blacklistage immédiat dans le CRM, sans possibilité de réactivation sans demande explicite du prospect

**Règles anti-spam :**
- Objet de l'email : jamais en majuscules, pas de « URGENT », « GRATUIT », « !! »
- Un seul lien externe maximum dans le corps du message
- Ratio texte/images : 100 % texte pour les cold emails
- Adresse d'envoi : domaine professionnel vérifié (SPF, DKIM, DMARC configurés)

**Suivi et traçabilité :**
- Enregistrer chaque envoi dans la fiche lead (`format_fiche_lead.md`)
- Taux d'ouverture cible : > 30 %
- Taux de réponse cible : > 5 %
- Alerter si taux de bounce > 5 % sur une séquence

## Exemples d'utilisation
1. Paramétrer les règles d'automatisation dans l'outil d'emailing (séquences, délais)
2. Vérifier la conformité d'une séquence de prospection avant lancement
3. Former un commercial JM Partners aux règles d'envoi

## Ne jamais faire
- Envoyer plus de 2 emails à un même prospect dans un délai de 30 jours
- Continuer à contacter un prospect après un opt-out, même via un autre canal
- Utiliser une adresse email générique (contact@, info@) comme expéditeur
