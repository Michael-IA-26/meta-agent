# Contributing — Meta-Agent

## Regles absolues

1. Zero commit direct sur main — tout passe par une PR
2. Toute PR doit etre reviewee par l autre avant merge — pas d exception
3. Zero secret en dur dans le code — tout passe par Doppler
4. Une PR ouverte = priorite — on la review avant d en ouvrir une nouvelle

## Workflow

1. Creer une branche : git checkout -b feat/ma-feature
2. Travailler et commiter
3. Pousser : git push origin feat/ma-feature
4. Ouvrir une PR sur GitHub
5. Attendre la review de l autre
6. Merger apres approbation

## Daily async

Chaque matin dans Telegram :
- Fait hier
- Bloque sur
- PRs en attente de review : numero

## Conventions de commit

- feat: nouvelle fonctionnalite
- fix: correction de bug
- docs: documentation
- test: tests
- ci: CI/CD
- refactor: refactoring sans nouvelle feature

## Securite

- Secrets via Doppler uniquement
- Tokens OAuth jamais dans Git (token*.json exclu par .gitignore)
- En cas de doute, ouvrir une issue avant de commiter
