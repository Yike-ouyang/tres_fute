Corrige les trois problèmes suivants dans le jeu React + TypeScript existant. Effectue les modifications dans le code en conservant les autres règles et le placement des bonus.

**1. Accorder les bonus de tour au début du tour**

Les bonus de tour doivent être accordés **au début de chaque tour global, à chacun des deux joueurs**, avant le premier lancer du joueur 1 :

| Tour global | Bonus pour chaque joueur |
| ----------- | ------------------------ |
| 1           | Relance                  |
| 2           | +1                       |
| 3           | Joker chiffre            |
| 4           | Dé bonus noir            |
| 5 et 6      | Aucun                    |

* Ne pas les accorder à la fin du tour ni au changement de joueur actif.
* Chaque récompense doit être accordée exactement une fois par joueur et par tour, même après un nouveau rendu React.
* Au démarrage et après une réinitialisation, attribuer immédiatement la relance du tour 1.
* Au tour 4, résoudre le bonus noir du joueur 1, puis celui du joueur 2, avant de lancer les dés.

**2. Résoudre immédiatement les bonus dés de couleur**

Les bonus dés jaune, turquoise, bleu foncé, marron, rose et noir **ne sont pas stockables**.

Supprimer la barre qui les compte, ainsi que les commandes permettant de les conserver ou de les utiliser ultérieurement. Conserver leurs icônes à leurs emplacements de déclenchement sur le plateau.

Lorsqu’un bonus de couleur est débloqué :

1. Terminer l’application du coup qui l’a déclenché.
2. Suspendre la progression normale du jeu.
3. Afficher immédiatement l’interface permettant de résoudre ce bonus pour son propriétaire.
4. Proposer les choix légaux selon les règles de ce bonus.
5. Appliquer le choix validé et résoudre les éventuels nouveaux bonus.
6. Reprendre le jeu uniquement lorsque tous les bonus immédiats en attente sont résolus.

Si plusieurs bonus sont obtenus simultanément, les résoudre successivement dans un ordre déterministe. Une file technique de résolution est autorisée ; elle ne constitue pas une réserve utilisable plus tard.

Si aucun coup légal n’est possible, afficher une explication et permettre de terminer la résolution sans effet. Ne pas conserver le bonus.

Les compteurs de **relance, joker chiffre et +1** restent en place : ce sont les seuls bonus stockables.

**3. Afficher le choix lors de chaque utilisation rose**

Actuellement, l’utilisation d’une case rose ne propose pas le choix attendu. Corriger le parcours de sélection et de validation.

Cette règle s’applique à toute utilisation rose : dé rose, blanc joué en rose, action passive, +1 ou bonus immédiat rose.

La destination reste la première case vide en partant de la gauche.

**Première case :**

Inscrire directement la valeur effective du dé, sans proposer de choix.

**Toutes les autres cases :**

Avant toute inscription définitive, ouvrir un panneau ou une boîte de dialogue présentant :

* La position de la case.
* La valeur effective utilisée.
* Le multiplicateur de la case.
* Le bonus associé.
* Les deux options et leur résultat.

| Option                 | Valeur inscrite                    | Récompense              |
| ---------------------- | ---------------------------------- | ----------------------- |
| « Prendre les points » | `valeurEffective × multiplicateur` | Aucun bonus             |
| « Prendre le bonus »   | `Math.ceil(valeurEffective / 2)`   | Bonus associé à la case |

Exemple : pour une valeur de 5 sur une case ×2, proposer **« Inscrire 10, sans bonus »** ou **« Inscrire 3 et obtenir le bonus »**.

Utiliser la valeur effective après application éventuelle d’un joker. Pour un bonus rose virtuel, utiliser la valeur choisie pendant sa résolution.

Conserver les multiplicateurs et les récompenses déjà configurés, notamment le renard de la neuvième case si la fonctionnalité de score est présente :

* Choisir les points ne débloque pas le renard.
* Choisir le bonus débloque le renard et inscrit la moitié arrondie au supérieur.
* Le renard ne provoque aucune action supplémentaire.

Si une case autre que la première n’a réellement aucun bonus configuré, afficher tout de même le panneau, mais désactiver l’option bonus avec la mention « Aucun bonus sur cette case ». Ne pas inventer de récompense.

**Validation et enchaînement :**

* Ne rien inscrire et ne consommer aucun dé, joker ou +1 avant la confirmation du choix.
* Une annulation revient à l’étape précédente sans modifier le plateau.
* Si l’action provient d’un bonus immédiat, revenir à sa sélection sans supprimer le bonus en attente.
* Après confirmation, appliquer le coup une seule fois.
* Si l’option bonus accorde une relance, un joker ou un +1, créditer son compteur.
* Si elle accorde un bonus de couleur, ouvrir immédiatement sa résolution.
* Ne pas passer à la manche ou à la phase suivante tant que cette résolution n’est pas terminée.

**4. Diagnostic et vérification**

Identifier pourquoi le choix rose ne s’ouvre pas : vérifier notamment les chemins qui inscrivent directement la valeur ou valident le coup avant l’ouverture du panneau. Faire converger toutes les utilisations roses vers la même logique de résolution.

Compléter les logs debug existants pour suivre :

* L’attribution des bonus de début de tour.
* Le déclenchement et la résolution des bonus immédiats.
* L’ouverture du choix rose.
* L’option choisie, la valeur inscrite et la récompense accordée.

Vérifier au minimum :

* L’obtention de la relance dès le démarrage.
* L’absence de double attribution au changement de joueur.
* La résolution des deux bonus noirs avant le premier lancer du tour 4.
* La disparition du compteur de bonus de couleur.
* Un enchaînement de bonus immédiats.
* Les deux options d’une case rose, y compris depuis un +1 et un bonus rose virtuel.
* L’annulation sans consommation et l’absence de double validation.

Effectuer les corrections, puis résumer la cause du problème rose, les changements apportés et les vérifications réalisées.
