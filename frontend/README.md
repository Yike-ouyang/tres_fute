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

Tout l'état est conservé côté front-end (React) pour le rendu des composants ;
le moteur de règles et les sessions de jeu vivent côté backend (`/api`).

## Onglets

`App.tsx` expose trois onglets : **Replay**, **Play** (humain vs humain,
hot-seat) et **Play against AI** (humain vs modèle).

## Interactions de jeu — clic = coup (aucune validation)

Dans **Play** et **Play against AI**, il n'y a **aucun** bouton « Valider » /
« Confirmer ». Le dernier clic joue toujours le coup :

- **Dé à destination unique** : un clic sur le dé joue immédiatement (le dé est
  sélectionné puis la seule destination est appliquée automatiquement).
- **Dé à plusieurs destinations** : 1ᵉʳ clic sur le dé = sélection (dé en
  surbrillance, cases légales surlignées) ; clic sur la case = coup joué.
- **Dé blanc** : dé → couleur → case (auto si la destination est unique).
- **Bonus bleu** : bonus → cellule → valeur. **Bonus turquoise immédiat** :
  ligne → colonne.
- **Joker** : joker → valeur 1–6. **Choix rose** : clic sur l'option.
- **Destination turquoise** (plusieurs lignes autorisées) : chaque clic ajoute
  une ligne (re-clic la retire) ; le coup part dès que l'ensemble atteint
  `maxPick` ou est maximal — `Échap` remet l'ensemble à zéro.
- **Phase passive** : les dés à choisir sont les dés **écartés** (carré gris,
  cliquables) ; dans le cas « fallback », ce sont les dés **placés dans les
  emplacements** du joueur (cliquables). Phase de remplissage : carré gris.
- **Joker chiffre** : la **valeur est choisie** (jetons « 3, 4, 5, 6 » puis wild) et les
  jetons peuvent être utilisés **dans n'importe quel ordre** ; utilisable en phase active,
  passive, +1 et remplissage (dès qu'il y a des dés à choisir).
- **+1** : ne porte que sur les dés du **joueur actif courant** (`chosen`) et la **zone
  grise** (`discarded`) — jamais les dés `available`.
- **Annulation** : `Échap` (ou le bouton « Annuler (Échap) ») annule la
  sélection en cours. Aucun coup n'est joué avant le dernier clic.

Le mapping clic → identifiant d'action v2 est testé dans
`src/playClicks.test.ts` (`npm test`).

## Compteurs de bonus (bandeau haut)

`StatusBar.tsx` regroupe, à côté du compteur de tour, les compteurs
**Relances**, **Jokers** et **+1** du joueur concerné, au format unique
**`dispo/total`** (ex. `Relances 2/3` = 2 disponibles sur 3 débloquées). Un
compteur à 0 disponible est grisé ; il est cliquable quand l'action
correspondante est légale.

## Sélection du modèle IA

Avant de démarrer une partie contre l'IA, un sélecteur liste les checkpoints
renvoyés par `GET /api/human_play/models` (`run / sous-dossier (fichier)`), le
plus récent étant présélectionné. Le bandeau de partie affiche
`Adversaire : run / sous-dossier (fichier)`. La conversion état → observation
du modèle est **entièrement backend** : le front ne reçoit jamais l'observation
numérique.

## Cases turquoise (avant / après)

| Élément | Avant | Après |
|---|---|---|
| Case vide | `#ffffff` (générique) | `#f2fbfa`, bordure `#6fb8b3` |
| Case cochée | `#c8e6c9` masquée par le style « dark » | `#00a99d`, bordure `#00695f`, **✓ blanc** |
| Triangle foncé coché | `#17726d` (identique au vide foncé) | `#00c2b2`, bordure `#00544c`, **✓ blanc** |

La distinction repose sur la **couleur saturée + la coche ✓** (pas uniquement
sur la teinte), ce qui reste lisible en daltonisme.

