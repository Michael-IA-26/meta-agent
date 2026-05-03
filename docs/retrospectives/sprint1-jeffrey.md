# Bilan Sprint 1 — Jeffrey

> Sprint du 28 avril au 2 mai 2026

---

## ✅ Livré

**Sprint 1 PromptFoo + CI — PR #13** (4 checks verts)
- **J1** PromptFoo installé (Node 24, npm 11, PromptFoo 0.121.8) — opérationnel
- **J2** Premier golden test sur agent email (1 cas, 5 assertions JSON, validation structure)
- **J3** 3 tests supplémentaires (LinkedIn, alerte Google, newsletter) — 4 catégories d'emails couvertes
- **J4** GitHub Actions CI : workflow `prompt-tests.yml` + secret `ANTHROPIC_API_KEY` → 4 checks verts à chaque PR
- **J5** Telegram bot : non requis (Mika l'a livré en PR #12)
- **J6** `onboarding-client.md` : à livrer ce weekend
- **J7** Grille validation utilisateur : à livrer ce weekend
- **J8** Review PR Sprint 1 Mika : dimanche / lundi matin
- **J9** Ce bilan : ✅

---

## 🎯 Compétences acquises (vs niveau Sprint 0)

**Que je sais faire seul maintenant** :
- Lire un fichier YAML, identifier les niveaux d'indentation, repérer une erreur de structure
- Écrire un golden test PromptFoo : prompt système + provider + assertions JS
- Manipuler des regex JS pour stripper du markdown (`output.replace(/.../g, '')`)
- Écrire un workflow GitHub Actions avec secrets et path filtering
- Récupérer le code d'un collègue avec `git merge main` et résoudre les retards de branche
- Lire un fichier `.py` Python (decorateurs, f-strings, try/except, fallbacks)
- Diagnostiquer une CI rouge en lisant les logs et reproduire en local

**Que j'ai appris à faire en pair-programming avec Claude** :
- Décortiquer un message d'erreur Python ou YAML
- Choisir entre 2 stratégies (assouplir un test vs durcir le prompt)
- Écrire des messages de commit Conventional (`feat:`, `test:`, `ci:`, `docs:`)
- Lire un workflow GitHub Actions existant pour s'en inspirer

---

## 🐛 Bugs / points à signaler à Mika

1. **Fichier au nom invalide sur Windows** :

Le caractère `:` rend impossible le `git checkout main` sur Windows. À renommer ou supprimer.

2. **Fichier fantôme** :

Faute de frappe avec un `œ` collé en fin de nom. À supprimer dans une PR cleanup.

3. **ICP non câblé** : `packages/prompts/icps/agence_conseil.md` existe mais n'est pas injecté dans le prompt système d'`analyzer.py`. Sans lui, Claude classe LinkedIn en `action_requise` et newsletter en `information` au lieu de `inutile`. J'ai dû assouplir 2 assertions PR #13.

4. **Force-push sur `main` détecté en fin de Sprint** : un force-push a réécrit l'historique de `main` (`9795be1` → `12db40c`), invalidant l'ancêtre commun de plusieurs branches feature en cours. Conséquence concrète : impossible de créer la PR J6 — GitHub Web et `gh` CLI ont retourné l'erreur `The jeffrey/sprint1-onboarding branch has no history in common with main`. Workaround appliqué : nouvelle branche `jeffrey/sprint1-onboarding-v2` créée depuis `origin/main`, cherry-pick du commit J6 (`68c7f1a`), push → PR #18. ~30 min perdues à diagnostiquer.

---

## 🔍 Questions pour la rétrospective

1. **ICP au M7** : tu prévois quand de câbler l'ICP dans le prompt système ? J'aimerais durcir mes 2 assertions assouplies dans la foulée.

2. **Charge S2 LeadCommercial** : sur S2 je dois faire Meta-Agent (schéma JSON brief, validate_brief.py, 5 tests) ET LeadCommercial (ICP JM Partners, scoring, Postman + Sirene). Si je dois prioriser, je commence par quoi ?

3. **Onboarding cabinet Vesper** : pour S13, faudrait-il que je commence à rédiger un guide d'onboarding LC dès S2-S3, avant que la doc soit obsolète ?

4. **Règle no-force-push sur `main`** : pour éviter que l'incident force-push se reproduise (ingérable quand on sera 3+ contributeurs avec les cabinets Vesper), on convient de :
   - Ne plus jamais `git push --force` sur `main`
   - Utiliser `git revert` pour annuler un commit fautif (commit inverse propre)
   - Activer les **branch protection rules** sur `main` (Require PR, Require status checks, Restrict deletions, No force pushes) ?

---

## 📝 Note libre

Sprint 1 a été dense mais structurant. Les 4 jours PromptFoo + CI m'ont fait basculer du *"j'apprends Python"* au *"j'écris des tests qui protègent l'agent et tournent en CI à chaque PR"*. C'est concret et utile.

Le 1er mai férié a décalé J6/J7/J8 sur le weekend, ce qui me convient bien. Sprint 1 fini lundi matin avant attaque S2.

L'envie d'attaquer LeadCommercial est forte — c'est la partie où mon expertise comptable va vraiment servir. Hâte de voir le 1er lead Sirene IDF arriver dans Supabase en S3.