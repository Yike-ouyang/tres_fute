Ajoute les règles suivantes à l’interface existante, toujours uniquement en **React + TypeScript**, sans back-end.

Conserve la disposition du plateau, ses dimensions et tous les identifiants existants. Implémente uniquement les règles décrites ici : aucun score, bonus, joueur passif ou règle supplémentaire du jeu original.

**1. Déroulement de la partie**

La partie comporte **6 tours**, chacun comprenant au maximum **3 manches**. Ici, une manche correspond à un lancer suivi du choix et de l’utilisation d’un dé.

Afficher le tour actuel et la manche actuelle.

Au début de chaque tour :

* Libérer les trois emplacements de dés choisis.
* Vider le carré gris des dés écartés.
* Remettre les six dés à disposition.
* Conserver toutes les cases remplies ou cochées sur le plateau.
* Lancer automatiquement les six dés pour commencer la première manche.

Les six dés ont une identité et une couleur permanentes : jaune, rose, marron, turquoise, bleu foncé et blanc. Chaque lancer donne à chaque dé disponible une valeur entière aléatoire entre 1 et 6.

Au début des manches suivantes, relancer uniquement les dés encore disponibles. Les dés choisis ou écartés conservent leur valeur.

**2. Sélection et validation d’un dé**

Le joueur clique sur un dé disponible, puis, si nécessaire, choisit sa destination sur le plateau.

Cette sélection est provisoire tant que le coup n’est pas terminé :

* Mettre en évidence uniquement les destinations autorisées.
* Désactiver les autres cases.
* Permettre d’annuler la sélection avant validation.
* Ne déplacer aucun dé et ne modifier aucune case avant la validation complète.

Si aucune destination n’est possible, afficher un message non bloquant, par exemple « Aucun coup possible avec ce dé », puis permettre au joueur de choisir un autre dé. Ne consommer ni le dé ni la manche.

Une fois le coup validé :

1. Appliquer son effet sur le plateau.
2. Placer le dé sélectionné dans l’emplacement correspondant à la manche : `die-1`, `die-2` ou `die-3`.
3. Déplacer tous les autres dés disponibles dont la valeur est **strictement inférieure** à celle du dé choisi dans un carré gris situé à gauche du plateau.
4. Conserver les dés de valeur égale ou supérieure parmi les dés disponibles.
5. Passer à la manche suivante et relancer les dés disponibles.

Après la troisième manche, déplacer tous les dés encore disponibles dans le carré gris et terminer le tour.

S’il ne reste aucun dé disponible avant la troisième manche, terminer le tour immédiatement.

Pour éviter un blocage, si aucun dé disponible ne permet de coup légal, même en utilisant le blanc, afficher un message et proposer un bouton « Terminer le tour ». Ce bouton déplace les dés restants dans le carré gris.

À la fin d’un tour, cocher automatiquement sa case `turn-{numéro}` et afficher un bouton « Tour suivant ». Après le sixième tour, afficher « Partie terminée » et désactiver les actions de jeu.

**3. Verrouillage du plateau**

Les cases du plateau ne sont plus modifiables manuellement :

* Une case cochée ne peut pas être décochée.
* Un nombre inscrit ne peut pas être modifié ou effacé.
* Les nombres sont inscrits automatiquement par le programme.
* Les clics sur les cases servent uniquement à choisir une destination autorisée pour le dé sélectionné.
* Le suivi des tours et les emplacements de dés sont pilotés par le jeu.
* Les compteurs de bonus restent visibles, mais désactivés et sans effet.

**4. Dé jaune**

La valeur du dé indique la colonne et la manche indique la ligne.

Exemple : un dé jaune de valeur 3 sélectionné à la manche 2 coche `yellow-r2-c3`.

Mettre en évidence cette unique destination et demander un clic dessus pour valider. Si elle est déjà cochée, le coup est impossible.

**5. Dé turquoise**

Le joueur peut cocher des cases libres dans la colonne correspondant à la valeur du dé.

Le nombre maximal de cases à cocher est :

**1 + le nombre de dés déjà choisis pendant ce tour dont la valeur est identique à celle du dé joué.**

Compter uniquement les dés présents dans les emplacements de sélection avant ce coup, quelle que soit leur couleur. Ne pas compter les dés disponibles ou écartés.

Exemple : si deux dés de valeur 4 ont déjà été choisis, jouer un turquoise de valeur 4 permet de cocher jusqu’à trois cases de la colonne 4.

Fonctionnement :

* Mettre en évidence toutes les cases libres de cette colonne.
* Permettre au joueur de sélectionner entre une case et le maximum autorisé, dans la limite des cases libres.
* Distinguer visuellement les sélections provisoires des coches définitives.
* Permettre de retirer une sélection provisoire.
* Afficher un bouton « Valider » actif dès qu’au moins une case est sélectionnée.

S’il ne reste aucune case libre dans la colonne, le coup est impossible.

**6. Dé rose**

La destination est la première case vide de gauche à droite.

La valeur inscrite est :

`Math.ceil(valeurDuDé / 2)`

Mettre en évidence la destination et demander un clic pour y inscrire automatiquement le résultat.

Si les douze cases sont remplies, le coup est impossible.

**7. Dé bleu foncé**

La piste comporte onze cases. `blue-cell-6` contient le **7 central fixe**, qui reste non modifiable.

Les deux branches progressent indépendamment :

* Branche droite : `blue-cell-7`, puis 8, 9, 10 et 11.
* Branche gauche : `blue-cell-5`, puis 4, 3, 2 et 1.

Ces numéros désignent les positions des cases, pas les valeurs à inscrire.

Calculer la somme de la valeur actuelle du dé bleu foncé et de celle du dé blanc, même si l’autre dé est déjà choisi ou écarté.

Pour chaque branche, utiliser comme référence le dernier nombre inscrit dans cette branche, ou **7** si elle est encore vide.

La somme peut être inscrite dans la prochaine case libre :

* À droite, si elle vaut exactement la référence + 1.
* À gauche, si elle vaut exactement la référence − 1.
* Sur l’une ou l’autre branche non pleine, si elle vaut **7**, quelle que soit la référence.

Ne jamais sauter de case.

Mettre en évidence les destinations légales et laisser le joueur cliquer sur celle de son choix. Inscrire automatiquement la somme.

Si aucune branche ne peut recevoir cette somme, le coup est impossible.

**8. Dé marron**

Une destination est légale si la case :

* Porte la même valeur que le dé.
* N’est pas cochée.
* Se trouve à droite de la dernière case marron cochée, s’il y en a une.

Si plusieurs destinations sont possibles, les mettre toutes en évidence et laisser le joueur choisir.

Après validation, cocher la case choisie. Toutes les cases non cochées situées à sa gauche deviennent définitivement inaccessibles et doivent apparaître visuellement désactivées.

Si aucune destination n’est légale, le coup est impossible.

**9. Dé blanc**

Lorsque le joueur sélectionne le dé blanc, afficher un choix parmi les cinq couleurs : jaune, turquoise, bleu foncé, marron et rose.

Le blanc applique les règles de la couleur choisie avec sa propre valeur. Pour le bleu foncé, utiliser toujours la somme **blanc + bleu foncé**.

Le dé reste physiquement blanc : ne pas changer sa couleur permanente. Seul le blanc est placé dans l’emplacement de dé choisi.

La mise à l’écart des dés strictement inférieurs se fait d’après la valeur du dé blanc, jamais d’après la somme bleu + blanc.

Une couleur sans coup légal doit être signalée comme indisponible. Permettre de revenir au choix des couleurs ou d’annuler la sélection du blanc.

**10. Réinitialisation et état React**

Ajouter un bouton « Réinitialiser la partie », disponible à tout moment.

Il doit :

* Effacer toutes les coches et les valeurs ajoutées.
* Restaurer les cases marron devenues inaccessibles.
* Conserver les nombres préimprimés, notamment le 7 central.
* Réinitialiser le suivi des tours et les compteurs.
* Vider les emplacements de dés choisis et le carré gris.
* Supprimer toute sélection provisoire et tout message.
* Recommencer au tour 1, manche 1, avec un nouveau lancer des six dés.

Utiliser un état React typé pour représenter la progression, les dés, le plateau et les sélections provisoires. Séparer les fonctions de calcul des coups légaux des composants d’affichage.

Vérifier notamment que les coups impossibles ne changent pas l’état du jeu, qu’un coup ne peut pas être validé deux fois et que les dés choisis ou écartés ne sont jamais relancés pendant le même tour.
