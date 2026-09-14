Ajoute le calcul et l’affichage des scores de fin de partie pour les deux joueurs, ainsi que les bonus **renard**, dans le jeu React + TypeScript existant.

Conserve les règles précédentes, sauf les changements explicitement indiqués ci-dessous. Utilise exactement les barèmes de ce prompt.

**1. Fin de partie et affichage**

Afficher les résultats uniquement lorsque le sixième tour global est entièrement terminé, après :

* La dernière action passive.
* Les dernières fenêtres d’utilisation des +1.
* La résolution de tous les bonus immédiats en attente.

Présenter un tableau comparatif :

| Catégorie                    | Joueur 1                | Joueur 2                |
| ---------------------------- | ----------------------- | ----------------------- |
| Jaune                        | Score                   | Score                   |
| Turquoise                    | Score                   | Score                   |
| Bleu foncé                   | Score                   | Score                   |
| Marron                       | Score                   | Score                   |
| Rose                         | Score                   | Score                   |
| Sous-total des cinq couleurs | Somme                   | Somme                   |
| Renards débloqués            | Nombre                  | Nombre                  |
| Valeur d’un renard           | Minimum des cinq scores | Minimum des cinq scores |
| Points des renards           | Nombre × valeur         | Nombre × valeur         |
| Total final                  | Total                   | Total                   |

Mettre en évidence le joueur ayant le total le plus élevé. Si les totaux sont identiques, afficher « Égalité », sans ajouter de règle de départage.

**2. Fonctionnement des renards**

Un renard est un bonus de score permanent :

* Il se débloque lorsque sa condition est remplie.
* Il ne provoque aucune action immédiate.
* Il ne se stocke pas dans les compteurs de relance, joker ou +1.
* Il ne se dépense pas.
* Chaque emplacement de renard ne peut être débloqué qu’une seule fois.

Afficher une icône de renard à chaque emplacement prévu, avec deux apparences distinctes : verrouillé et débloqué.

Pour chaque joueur :

`valeurRenard = Math.min(scoreJaune, scoreTurquoise, scoreBleu, scoreMarron, scoreRose)`

`pointsRenards = nombreRenardsDebloques * valeurRenard`

`scoreTotal = scoreJaune + scoreTurquoise + scoreBleu + scoreMarron + scoreRose + pointsRenards`

Si une couleur vaut zéro point, chaque renard vaut zéro point. Ne jamais inclure les points des renards dans le calcul du minimum.

**3. Score jaune**

Calculer séparément les points de chacune des trois lignes, puis les additionner.

| Cases cochées dans une ligne | Points |
| ---------------------------- | ------ |
| 0                            | 0      |
| 1                            | 2      |
| 2                            | 6      |
| 3                            | 12     |
| 4                            | 20     |
| 5                            | 30     |
| 6                            | 42     |

**Renard jaune :** le placer dans la deuxième ligne de bonus, en sixième et dernière position, entre les cases de colonne 6 des lignes 2 et 3.

Il se débloque lorsque ces deux cases sont cochées. **Il remplace le bonus +1 précédemment présent à cet emplacement.**

**4. Score turquoise**

Calculer séparément les points de chacune des cinq lignes, puis les additionner.

Pour le score, compter **toutes les cases cochées**, claires comme foncées.

| Cases cochées dans une ligne | Points |
| ---------------------------- | ------ |
| 0                            | 0      |
| 1                            | 1      |
| 2                            | 3      |
| 3                            | 6      |
| 4                            | 10     |
| 5                            | 15     |
| 6                            | 21     |

**Renard turquoise :** le placer à droite de la première ligne. Il se débloque lorsque les six cases de cette ligne sont cochées.

**5. Score bleu foncé**

Calculer indépendamment la progression à gauche et à droite du 7 central.

Pour chaque branche, utiliser le nombre de cases remplies depuis le centre :

| Cases remplies dans une branche | Points de progression |
| ------------------------------- | --------------------- |
| 0                               | 0                     |
| 1                               | 3                     |
| 2                               | 6                     |
| 3                               | 9                     |
| 4                               | 13                    |
| 5                               | 17                    |
| 6                               | 22                    |

Ce barème donne le score de progression de toute la branche : **ne pas additionner les points des étapes intermédiaires**.

Le 7 central préimprimé ne compte pas comme une case remplie. Inscrire un nouveau 7 dans une branche ne remet pas sa progression à zéro.

Ajouter ensuite **4 points pour chaque case contenant une valeur parmi `2, 3, 4, 10, 11, 12`**, sur les deux branches.

`scoreBleu = progressionGauche + progressionDroite + 4 * nombreValeursSpeciales`

Exemple : trois cases remplies à gauche et quatre à droite rapportent `9 + 13 = 22` points de progression. Si deux cases contiennent une valeur spéciale, le score bleu vaut `22 + 8 = 30`.

**Renard bleu :** le placer à l’extrémité droite, sur la case 13. Il se débloque dès que cette case est remplie.

**6. Score marron**

Le score dépend du **nombre total de cases cochées**, pas de la position de la dernière coche.

Les cases sautées et devenues inaccessibles ne comptent pas.

| Cases cochées | Points |
| ------------- | ------ |
| 0             | 0      |
| 1             | 3      |
| 2             | 5      |
| 3             | 9      |
| 4             | 14     |
| 5             | 20     |
| 6             | 27     |
| 7             | 35     |
| 8             | 44     |
| 9             | 54     |
| 10            | 65     |
| 11            | 77     |
| 12            | 90     |

**Renard marron :** le placer entre les cases 11 et 12, portant respectivement les valeurs 6 et 3. Il se débloque uniquement lorsque ces deux cases sont cochées.

**7. Score rose**

Le score rose est la **somme des valeurs effectivement inscrites dans les douze cases**. Une case vide rapporte zéro.

Les multiplicateurs ou divisions ayant déjà été appliqués au moment de l’inscription, ne pas les appliquer une seconde fois au calcul du score.

**Renard rose :** le placer sous la neuvième case, dont le multiplicateur reste ×3.

Cette case propose désormais le choix habituel :

* **Option points :** inscrire `valeurEffective * 3`, sans débloquer le renard.
* **Option bonus :** inscrire `Math.ceil(valeurEffective / 2)` et débloquer le renard.

Remplir la neuvième case ne suffit donc pas à obtenir le renard : il faut avoir choisi l’option bonus. Mémoriser explicitement ce choix.

**8. Intégration technique**

* Créer une fonction pure et typée de calcul du score à partir de l’état d’un joueur, réutilisée pour les deux joueurs.
* Calculer les scores depuis le plateau, sans maintenir de total incrémental susceptible d’être compté deux fois.
* Donner un identifiant stable à chaque renard, avec le préfixe du joueur.
* Intégrer le déblocage des renards à la détection des récompenses existante, sans les ajouter à la file des actions immédiates.
* Autoriser leur déblocage par toute action légale : active, passive, +1 ou bonus immédiat.
* Ajouter aux logs debug le déblocage d’un renard et le détail du calcul final.
* Réinitialiser les renards et masquer les résultats lorsque la partie est réinitialisée.

**9. Vérifications attendues**

Vérifier notamment :

* Un plateau vide donne zéro dans toutes les catégories.
* Une couleur à zéro rend tous les renards sans valeur.
* Chaque barème traite correctement zéro case et une zone entièrement remplie.
* Trois cases bleues donnent 9 points de progression, quatre en donnent 13.
* Les valeurs bleues spéciales rapportent chacune exactement 4 points supplémentaires.
* Les cases marron bloquées ne comptent pas.
* Le renard rose est obtenu uniquement avec l’option bonus.
* Un renard ne peut pas être comptabilisé deux fois.
* Les résultats attendent la fin des dernières actions et résolutions de bonus.

Effectuer les modifications dans le code, puis résumer les changements et les vérifications réalisées.
