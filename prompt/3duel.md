Fais évoluer le jeu existant vers une version **à deux joueurs sur le même écran**, toujours uniquement en React + TypeScript.

Conserve les règles précédentes, sauf les modifications décrites ci-dessous. N’ajoute aucun bonus ni calcul de score.

**1. Affichage et plateaux indépendants**

Afficher deux plateaux :

* **Joueur 1 à gauche.**
* **Joueur 2 à droite.**

Chaque joueur possède son propre état : cases cochées, nombres inscrits, cases marron bloquées et emplacements de dés choisis.

Préfixer tous les identifiants propres à un plateau par `p1-` ou `p2-` pour garantir leur unicité. Exemples : `p1-yellow-r1-c5`, `p2-yellow-r1-c5`.

Les six dés constituent un ensemble commun. Afficher clairement les dés disponibles et le carré gris contenant les dés écartés.

Indiquer en permanence :

* Le tour global actuel, de 1 à 6.
* Le joueur actif.
* Le joueur qui doit agir.
* La phase actuelle : manche active 1, 2 ou 3, ou choix passif.

Seul le plateau du joueur qui doit agir peut recevoir une action. Sur petit écran, les deux plateaux peuvent être empilés.

**2. Déroulement d’un tour global**

La partie comporte **6 tours globaux**. Chaque tour suit cet ordre :

1. Le joueur 1 est actif et joue jusqu’à trois manches, selon les règles précédentes.
2. Le joueur 2 joue une action passive en choisissant un dé dans le carré gris du joueur 1.
3. Le joueur 2 devient actif et joue jusqu’à trois manches avec les six dés remis à disposition et relancés.
4. Le joueur 1 joue une action passive en choisissant un dé dans le carré gris du joueur 2.
5. Le tour global se termine.

Le joueur 1 commence chaque tour global.

Cocher la case du tour sur les deux plateaux uniquement après ces quatre phases de jeu. Après la dernière action passive du sixième tour, afficher « Partie terminée ».

Si la séquence active se termine avant trois manches selon les règles précédentes, passer directement au choix passif.

**3. Passage du jeu actif au choix passif**

À la fin d’une séquence active :

* Placer dans le carré gris tous les dés restants qui n’ont pas été choisis.
* Conserver dans ce carré les dés déjà écartés pendant les manches précédentes.
* Ne relancer aucun dé avant la fin du choix passif.
* Conserver aussi les valeurs des dés placés dans les emplacements du joueur actif.

Le joueur passif choisit **un seul dé du carré gris** et l’utilise sur son propre plateau.

Cette action :

* Ne consomme pas une manche de sa future séquence active.
* Ne provoque aucun lancer ni mise à l’écart d’autres dés.
* Ne place pas le dé dans ses emplacements de dés choisis.
* Peut permettre plusieurs coches si le dé est joué en turquoise.

Conserver le contenu du carré gris pendant toute la résolution de l’action passive, notamment pour calculer les coches turquoise supplémentaires.

**4. Règles du joueur actif**

Pendant ses trois manches actives, chaque joueur applique exactement les règles déjà implémentées.

Les exceptions jaune et turquoise ci-dessous concernent **uniquement le choix passif**.

**5. Dé jaune pendant le choix passif**

Le joueur passif peut cocher uniquement les six cases suivantes, en respectant la valeur du dé :

| Valeur du dé | Destination autorisée sur son plateau |
| ------------ | ------------------------------------- |
| 1            | Ligne 3, colonne 1                    |
| 2            | Ligne 3, colonne 2                    |
| 3            | Ligne 2, colonne 3                    |
| 4            | Ligne 2, colonne 4                    |
| 5            | Ligne 1, colonne 5                    |
| 6            | Ligne 1, colonne 6                    |

La manche à laquelle le dé a été écarté n’intervient pas.

Si la destination est déjà cochée, le coup est impossible.

Distinguer visuellement ces six cases sur les deux plateaux, par exemple avec un fond grisé, tout en conservant une apparence claire lorsqu’elles sont cochées.

**6. Dé turquoise pendant le choix passif**

La valeur du dé indique toujours la colonne turquoise à utiliser.

Le nombre maximal de cases à cocher est :

**1 + le nombre d’autres dés du carré gris ayant la même valeur que le dé sélectionné.**

Compter toutes les couleurs, mais :

* Ne pas compter deux fois le dé sélectionné.
* Ne pas compter les dés placés dans les emplacements du joueur actif.
* Ne pas compter les dés choisis précédemment par le joueur passif.

Exemple : si le carré gris contient un turquoise 4, un rose 4 et un marron 4, choisir le turquoise permet de cocher jusqu’à trois cases libres de la colonne 4.

Conserver la sélection provisoire et le bouton « Valider » existants. Le joueur doit choisir au moins une case et au maximum le nombre autorisé, dans la limite des cases libres.

**7. Autres couleurs pendant le choix passif**

Les dés rose, marron et bleu foncé conservent leurs règles précédentes et s’appliquent au plateau du joueur passif.

Pour le bleu foncé, calculer la somme **bleu foncé + blanc** à partir des valeurs conservées, que l’autre dé soit dans le carré gris ou dans un emplacement du joueur actif.

Le blanc permet toujours de choisir une des cinq couleurs :

* S’il est joué en jaune, appliquer les restrictions du jaune passif.
* S’il est joué en turquoise, compter les autres dés de même valeur présents dans le carré gris.
* S’il est joué en bleu foncé, utiliser la somme blanc + bleu foncé.
* Sinon, appliquer les règles habituelles de la couleur choisie.

**8. Coups impossibles et validation**

La sélection d’un dé reste provisoire jusqu’à la validation complète de son utilisation.

Si le dé ne permet aucun coup légal, afficher un message non bloquant et permettre au joueur passif de choisir un autre dé, sans modifier le plateau ni terminer sa phase.

Si aucun dé du carré gris ne permet de coup légal, y compris via les couleurs possibles du blanc, afficher « Aucun coup possible » et proposer un bouton « Passer ». Ne pas autoriser de sélection parmi les dés conservés par le joueur actif.

Après une action passive validée, ou après avoir passé, afficher un bouton pour poursuivre vers la phase suivante. Empêcher toute seconde action passive.

**9. État et réinitialisation**

Séparer explicitement dans l’état React :

* Les données des deux plateaux.
* Le tour global.
* Le joueur actif et le joueur qui doit agir.
* La phase active ou passive et le numéro de manche active.
* Les six dés, leurs valeurs et leurs emplacements.
* La sélection provisoire.

Au début de chaque nouvelle séquence active, remettre les six dés à disposition, vider le carré gris et libérer les emplacements de sélection. Conserver la progression des deux plateaux.

Le bouton « Réinitialiser la partie » réinitialise les deux joueurs et recommence au tour global 1, joueur 1 actif, manche 1.

Vérifier qu’une action ne modifie que le plateau du joueur concerné, que les restrictions passives ne s’appliquent pas aux manches actives et qu’un tour global ne se termine qu’après l’action passive du joueur 1.
