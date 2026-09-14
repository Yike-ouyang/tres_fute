Corrige le placement visuel des bonus dans le plateau React + TypeScript existant, pour les deux joueurs.

**Exigence principale : chaque bonus doit être physiquement placé à l’emplacement décrit ci-dessous, directement associé aux cases qui le déclenchent. Une liste ou une rangée générique de bonus en bas d’une zone ne satisfait pas cette demande.**

Conserve les interactions et la logique des bonus. Cette modification porte sur leur disposition et leur association visuelle avec les cases.

Les tableaux ci-dessous sont la référence pour cette version. N’ajoute aucun symbole qui n’y figure pas.

**1. Dimensions et repérage**

* Jaune : 3 lignes × 6 colonnes.
* Turquoise : **5 lignes × 6 colonnes**.
* Bleu foncé : **13 cases**, dont le 7 central fixe en position 7.
* Marron : 12 cases.
* Rose : 12 cases.

Toutes les positions sont numérotées **de gauche à droite**, et les lignes **de haut en bas**.

Conserver des identifiants uniques avec les préfixes `p1-` et `p2-`.

**2. Principes obligatoires de placement**

Chaque symbole doit être ancré à sa cible :

* Bonus entre deux cases verticales : centré dans l’espace séparant ces deux cases, dans leur colonne.
* Bonus entre deux cases horizontales : centré dans l’espace séparant ces deux cases, à leur hauteur.
* Bonus de ligne : placé immédiatement à droite de la ligne correspondante.
* Bonus de colonne : placé immédiatement sous la colonne correspondante.
* Bonus d’une case : placé directement sous cette case, centré sur elle.
* Multiplicateur : placé directement au-dessus de sa case.

Une position indiquée « Aucun » reste vide, **sans décaler les symboles suivants**.

Prévoir suffisamment d’espace pour les icônes : elles ne doivent masquer ni les valeurs ni les zones cliquables.

**3. Suivi des tours**

Placer chaque bonus directement sous le numéro du tour correspondant :

| Tour | Bonus         |
| ---- | ------------- |
| 1    | Relance       |
| 2    | +1            |
| 3    | Joker chiffre |
| 4    | Dé bonus noir |
| 5    | Aucun         |
| 6    | Aucun         |

Utiliser six colonnes communes pour aligner les numéros et leurs bonus.

**4. Compteurs de bonus**

Conserver les représentations suivantes :

* Relance : cercle avec symbole de relance.
* Joker chiffre : icône de dé ; emplacements `3, 4, 5, 6, ?, ?`.
* +1 : symbole `+1`.
* Bonus immédiat : petit carré de la couleur correspondante.

Placer les récompenses de compteur **immédiatement à droite du dernier emplacement de leur piste** :

* Bonus marron à l’extrémité du compteur de jokers.
* Bonus rose à l’extrémité du compteur de +1.

Ces récompenses ne sont pas des cases supplémentaires du compteur. Les distinguer visuellement tout en montrant leur rattachement à la piste.

**5. Zone jaune : bonus entre les lignes**

Construire la zone avec **cinq rangées visuelles alternées** :

1. Cases de la ligne 1.
2. Première rangée de bonus.
3. Cases de la ligne 2.
4. Deuxième rangée de bonus.
5. Cases de la ligne 3.

Les cinq rangées partagent exactement les mêmes six colonnes.

| Colonne | Entre les lignes 1 et 2 | Entre les lignes 2 et 3 |
| ------- | ----------------------- | ----------------------- |
| 1       | Relance                 | Joker chiffre           |
| 2       | Joker chiffre           | Turquoise               |
| 3       | Rose                    | Bleu foncé              |
| 4       | +1                      | Marron                  |
| 5       | Turquoise               | Jaune                   |
| 6       | Aucun                   | +1                      |

**Interdiction de placer ces deux rangées de bonus sous la grille jaune.** Chaque symbole doit apparaître entre les deux cases qui le déclenchent.

**6. Zone turquoise : bonus à droite et en dessous**

Les cases foncées sont :

| Ligne | Colonnes foncées |
| ----- | ---------------- |
| 1     | 1 à 6            |
| 2     | 1 à 5            |
| 3     | 1 à 4            |
| 4     | 1 à 3            |
| 5     | 1 et 2           |

Réserver une colonne supplémentaire à droite pour les bonus de ligne :

| Ligne | Bonus immédiatement à droite |
| ----- | ---------------------------- |
| 1     | Aucun                        |
| 2     | +1                           |
| 3     | Marron                       |
| 4     | Turquoise                    |
| 5     | Aucun                        |

Réserver une rangée supplémentaire sous la grille pour les bonus de colonne :

| Colonne | Bonus directement en dessous |
| ------- | ---------------------------- |
| 1       | Marron                       |
| 2       | Rose                         |
| 3       | Jaune                        |
| 4       | Joker chiffre                |
| 5       | Bleu foncé                   |
| 6       | Relance                      |

Les bonus de ligne doivent être centrés verticalement sur leur ligne. Les bonus de colonne doivent être centrés horizontalement sur leur colonne.

**Ne pas regrouper les bonus de ligne avec ceux de colonne sous la grille.**

**7. Piste bleu foncé : bonus sous leur case**

Utiliser treize colonnes alignées pour les cases et les emplacements de bonus.

| Position de la case | Bonus directement en dessous |
| ------------------- | ---------------------------- |
| 1                   | +1                           |
| 2                   | Rose                         |
| 3                   | Aucun                        |
| 4                   | Jaune                        |
| 5                   | Joker chiffre                |
| 6                   | Aucun                        |
| 7 — centre fixe     | Aucun                        |
| 8                   | Aucun                        |
| 9                   | Relance                      |
| 10                  | Marron                       |
| 11                  | Aucun                        |
| 12                  | Turquoise                    |
| 13                  | Aucun                        |

Conserver les emplacements vides pour que chaque bonus reste exactement sous sa case. Ne pas compacter les sept symboles dans une liste.

**8. Piste marron : bonus entre les cases**

Les douze cases portent les valeurs :

`1, 5, 3, 4, 2, 6, 4, 5, 2, 1, 6, 3`

Placer les bonus **dans les intervalles horizontaux entre les cases**, et non dans une rangée sous la piste.

| Intervalle entre les positions | Bonus         |
| ------------------------------ | ------------- |
| 1 et 2                         | Joker chiffre |
| 2 et 3                         | Rose          |
| 3 et 4                         | Aucun         |
| 4 et 5                         | Relance       |
| 5 et 6                         | Turquoise     |
| 6 et 7                         | Aucun         |
| 7 et 8                         | +1            |
| 8 et 9                         | Bleu foncé    |
| 9 et 10                        | Aucun         |
| 10 et 11                       | Jaune         |
| 11 et 12                       | Aucun         |

Utiliser une structure alternant **case, intervalle de bonus, case**, avec onze intervalles réservés. Un intervalle vide doit conserver son espace.

Chaque symbole doit visuellement relier les deux cases nécessaires à son déclenchement.

**9. Piste rose : multiplicateur au-dessus, bonus en dessous**

Construire une grille commune à douze colonnes et trois rangées :

1. Multiplicateurs.
2. Cases numériques.
3. Bonus.

| Position | Multiplicateur au-dessus | Bonus en dessous |
| -------- | ------------------------ | ---------------- |
| 1        | Aucun affiché            | Aucun            |
| 2        | ×1                       | Relance          |
| 3        | ×2                       | Bleu foncé       |
| 4        | ×2                       | +1               |
| 5        | ×1                       | Joker chiffre    |
| 6        | ×2                       | Jaune            |
| 7        | ×2                       | Marron           |
| 8        | ×1                       | Relance          |
| 9        | ×3                       | Aucun            |
| 10       | ×2                       | Bleu foncé       |
| 11       | ×2                       | Turquoise        |
| 12       | ×3                       | Noir             |

Chaque multiplicateur et chaque bonus doivent être centrés sur **leur propre case**. Ne pas déplacer les symboles pour combler les positions vides.

**10. Structure React et CSS**

* Définir les positions dans des données typées : zone, type de bonus, case ou intervalle associé.
* Utiliser ces mêmes associations pour le rendu et la détection du déclenchement afin d’éviter les divergences.
* Privilégier CSS Grid avec des colonnes et rangées partagées.
* Éviter les coordonnées absolues calculées pour une seule taille d’écran.
* Donner aux sources de bonus des identifiants stables, par exemple `p1-yellow-between-r1-r2-c3` ou `p2-brown-between-c4-c5`.
* Distinguer visuellement les bonus non débloqués et débloqués sans changer leur emplacement.
* Préserver les clics sur les cases : aucun symbole décoratif ne doit intercepter les interactions.
* Les icônes de récompense sur le plateau indiquent leur source ; l’utilisation des bonus stockés reste accessible dans leurs compteurs.

**11. Adaptation aux petits écrans**

Conserver les relations spatiales à toutes les tailles :

* Empiler les plateaux des joueurs si nécessaire.
* Réduire raisonnablement les espacements.
* Si une piste devient trop large, autoriser son défilement horizontal en faisant défiler ensemble les cases et leurs symboles.

Ne jamais déplacer les bonus vers un bloc récapitulatif en bas pour faire tenir la mise en page.

**12. Vérification visuelle obligatoire**

Après implémentation, vérifier les deux plateaux sur un écran large et un écran étroit :

* Les bonus jaunes sont réellement entre les lignes.
* Les bonus turquoise sont à droite de leur ligne ou sous leur colonne.
* Les bonus bleus sont sous les bonnes positions, en comptant le centre comme case 7.
* Les bonus marron sont entre les cases.
* Les multiplicateurs roses sont au-dessus et les bonus sous les cases correspondantes.
* Les positions vides ne provoquent aucun décalage.
* Aucun symbole ne masque une valeur ou ne bloque un clic.

Si un navigateur est disponible, prendre des captures et les inspecter. Sinon, préciser que la vérification visuelle reste à effectuer.

**Résultat attendu : modifier le code pour obtenir ces placements exacts. Un affichage de tous les bons bonus au mauvais endroit ne constitue pas une implémentation valide.**
