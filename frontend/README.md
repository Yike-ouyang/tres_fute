# Plateau de dés — Frontend

Interface de plateau de jeu de dés en React + TypeScript (Vite). Plateau
interactif manipulable manuellement, sans logique de jeu : aucun calcul de
score, aucune validation des coups, aucun bonus automatique, aucun lancer
automatique de dés.

## Prérequis

- Node.js 18+ et npm

## Installation

```bash
cd frontend
npm install
```

## Lancer en développement

```bash
npm run dev
```

Puis ouvrir l'URL affichée (par défaut http://localhost:5173).

## Build de production

```bash
npm run build
npm run preview
```

## Contenu du plateau

- Barre de suivi des 6 tours (`turn-1` … `turn-6`).
- 3 compteurs de bonus de 7 cases (`bonus-{barre}-cell-{position}`).
- 3 emplacements de dés (`die-1` … `die-3`) avec sélection manuelle de la
  valeur (`die-{n}-value`) et de la couleur (`die-{n}-color`).
- Zone jaune 3×6 (`yellow-r{ligne}-c{colonne}`).
- Zone turquoise 6×6 (`turquoise-r{ligne}-c{colonne}`).
- Piste bleu foncé de 11 cases, case centrale fixe `blue-cell-6` = 7.
- Piste marron de 12 cases à cocher (`brown-cell-1` … `brown-cell-12`).
- Piste rose de 12 cases de saisie (`pink-cell-1` … `pink-cell-12`).

Tout l'état est conservé côté front-end (React), sans back-end ni base de
données.
