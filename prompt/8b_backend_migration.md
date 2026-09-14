Migre le jeu existant vers un **moteur Python indépendant**, exposé au front React + TypeScript par **FastAPI**.

Effectue les modifications dans le projet et vérifie le fonctionnement de bout en bout. Ne te limite pas à proposer une architecture ou à créer des fichiers vides.

**1. Résultat attendu**

L’architecture finale doit permettre deux usages :

* Jeu humain : React → requêtes HTTP → FastAPI → moteur Python.
* Simulation et futur entraînement RL : appels Python directs → moteur Python.

Le moteur doit fonctionner sans navigateur, sans serveur HTTP et sans dépendance à React.

FastAPI transporte les commandes et les réponses. Il ne contient pas les règles du jeu.

Le front affiche l’état reçu et transmet les décisions de l’utilisateur. Il ne calcule plus les coups légaux, les scores, les bonus ou les transitions.

Ne développe pas encore d’algorithme RL.

**2. Examiner l’existant avant modification**

Lire `REGLES_DU_JEU.md`, le code actuel et les tests disponibles.

Identifier :

* Les structures de données.
* Les fonctions de règles et de score.
* La gestion des dés et de l’aléatoire.
* Les phases actives, passives et +1.
* Les bonus et leurs enchaînements.
* L’avance automatique.
* Les composants React dépendant actuellement des règles.

Prendre `REGLES_DU_JEU.md` comme spécification, en tenant compte des corrections explicites ultérieures disponibles.

Vérifier notamment que la première case rose reçoit obligatoirement `ceil(valeurEffective / 2)`, sans bonus.

Ne pas reproduire silencieusement un bug du front en Python. Signaler les contradictions importantes et les décisions non résolues. Si le document manque, rechercher les spécifications présentes dans le projet et indiquer les limites avant d’inventer des règles.

Conserver les modifications préexistantes de l’utilisateur.

**3. Organiser le code**

Adapter l’organisation au projet existant, avec une séparation équivalente à :

* `backend/game_engine/` : état, actions, règles, transitions, bonus et scores.
* `backend/api/` : FastAPI, modèles de requêtes et réponses, gestion des parties.
* `backend/simulation/` : politiques automatiques et exécution des simulations.
* `backend/tests/` : tests du moteur et de l’API.
* Front existant : composants et client API.

Utiliser des types Python explicites. Les types internes du moteur doivent rester indépendants des objets HTTP de FastAPI.

**4. Construire le moteur Python**

Le moteur possède l’état officiel de chaque partie :

* Plateaux des deux joueurs.
* Dés, valeurs physiques et emplacements.
* Valeurs effectives nécessaires à une action.
* Tour, manche et phase.
* Joueur devant agir.
* Bonus disponibles, utilisés et en attente.
* Sources de récompenses déjà déclenchées.
* Renards et décisions en cours.
* Aléatoire propre à la partie.

Prévoir une interface Python documentée permettant au minimum de :

* Créer une partie avec une graine optionnelle.
* Obtenir le joueur devant agir et la décision attendue.
* Obtenir les choix légaux.
* Appliquer une action.
* Obtenir une observation pour un joueur.
* Calculer les scores.
* Déterminer si la partie est terminée.

Ne pas utiliser un état global partagé entre toutes les parties.

Une action invalide doit être refusée sans modifier l’état, consommer une ressource ou avancer le générateur aléatoire.

**5. Représenter explicitement les décisions**

Construire des phases et transitions explicites.

Après une action, le moteur exécute les conséquences automatiques jusqu’au prochain véritable choix ou jusqu’à la fin de partie.

Les choix doivent couvrir notamment :

* Dé et destination.
* Couleur du blanc.
* Option rose.
* Sélection turquoise.
* Joker et valeur.
* Résolution d’un bonus immédiat.
* Utilisation ou fin d’une fenêtre +1.
* Complément sans effet des emplacements actifs.
* Passage autorisé.

Ne pas obliger le futur agent RL à reproduire des opérations visuelles telles qu’ouvrir une fenêtre ou cliquer sur un bouton de confirmation.

Pour les choix complexes, utiliser des décisions successives ou une description structurée des paramètres autorisés. Éviter d’énumérer inutilement toutes les combinaisons de cases turquoise.

Le moteur reste responsable de la validation finale de chaque action.

**6. Garantir l’aléatoire reproductible**

Utiliser un générateur aléatoire dédié à chaque partie, initialisé par une graine optionnelle.

Prévoir un historique des actions acceptées permettant de reproduire un scénario avec la même version des règles.

Séparer l’aléatoire des dés de celui de la politique automatique.

Ne pas exposer l’état interne du générateur dans les observations du joueur ou du futur agent.

**7. Exposer une API FastAPI**

Mettre en place un contrat équivalent à :

| Méthode et route                | Fonction                       |
| ------------------------------- | ------------------------------ |
| `POST /games`                   | Créer une partie               |
| `GET /games/{game_id}`          | Lire son état visible          |
| `POST /games/{game_id}/actions` | Soumettre une décision         |
| `POST /games/{game_id}/reset`   | Réinitialiser la partie        |
| `POST /games/{game_id}/advance` | Lancer l’avance automatique    |
| `GET /health`                   | Vérifier que le serveur répond |

Chaque réponse de jeu doit fournir les éléments nécessaires au front :

* Identifiant et version de la partie.
* État visible des deux plateaux et des dés.
* Joueur devant agir.
* Phase et décision attendue.
* Choix autorisés.
* Scores détaillés.
* Événements utiles à l’affichage.
* Indicateur de fin de partie.

Les commandes doivent transmettre une intention, jamais un plateau modifié par le client.

Utiliser des modèles de requêtes et réponses typés. Distinguer la validation du format par l’API de la validation des règles par le moteur.

**8. Empêcher les incohérences réseau**

Inclure dans les commandes :

* Un identifiant unique de commande.
* La version de l’état sur laquelle le joueur a pris sa décision.

Garantir qu’une commande répétée ne s’applique pas deux fois. Refuser proprement une commande fondée sur une version dépassée et permettre au front de récupérer l’état courant.

Sérialiser les modifications d’une même partie pour éviter deux transitions concurrentes.

Pour cette première version, un stockage en mémoire est acceptable. Documenter alors que :

* Un redémarrage perd les parties.
* Le serveur doit utiliser un seul processus de travail.
* Les deux plateaux sur le même navigateur ne constituent pas un système d’authentification multijoueur.

Ne pas ajouter de base de données ou de comptes utilisateurs sans nécessité.

**9. Connecter React à l’API**

Conserver l’apparence du plateau, les identifiants des cases et le placement exact des bonus.

Remplacer la logique métier du front par un client API typé.

React peut conserver uniquement l’état d’interface :

* Fenêtres ouvertes.
* Sélections provisoires.
* Animations.
* État de chargement.
* Messages d’erreur.

Les destinations légales et les options proposées viennent du serveur. Le front peut présélectionner une destination unique, mais ne doit pas recalculer sa légalité.

Après validation, afficher l’état confirmé par le serveur.

Gérer :

* Les requêtes en cours et doubles clics.
* Les erreurs réseau sans fausse validation.
* Les réponses obsolètes.
* La récupération de l’état d’une partie.
* L’indisponibilité du serveur avec un message clair.

Configurer l’URL de l’API par variable d’environnement et les origines CORS nécessaires au développement.

Supprimer la logique métier TypeScript devenue inutile une fois la migration vérifiée.

**10. Migrer l’avance automatique**

Déplacer la simulation en Python. Elle utilise les mêmes décisions et transitions que le jeu humain, sans requête HTTP entre chaque coup.

Conserver ses comportements :

* Validation entièrement automatique.
* Résolution des bonus et choix intermédiaires.
* Arrêt exact après le nombre de tours demandé.
* Arrêt à la fin de partie.
* Protection contre les boucles infinies.

La préférence qui évite les dés les plus élevés aux manches actives 1 et 2 appartient à la **politique automatique**, pas aux règles du moteur.

Elle ne doit donc pas restreindre les actions accessibles à un humain ou au futur agent RL.

Ne pas bloquer le serveur pendant une avance longue. Prévoir une exécution contrôlée avec progression consultable et empêcher les commandes manuelles concurrentes sur la même partie.

**11. Préparer l’utilisation RL**

Fournir un script Python d’exemple qui :

1. Crée une partie sans FastAPI.
2. Choisit des actions légales pour les deux joueurs.
3. Résout une partie complète.
4. Affiche les scores finaux.
5. Peut répéter l’expérience avec plusieurs graines.

Le moteur calcule les scores, mais ne fixe pas la récompense d’apprentissage. Celle-ci appartiendra au futur adaptateur RL.

Documenter comment identifier le joueur devant agir et obtenir une observation complète des informations auxquelles il a droit, incluant la phase et les décisions en attente.

**12. Vérifier la migration**

Créer des tests significatifs à partir des scénarios de `REGLES_DU_JEU.md`.

Couvrir en priorité :

* Première case rose et choix des cases suivantes.
* Valeurs physiques et effectives avec joker.
* Turquoise dans les différents contextes.
* Progression bleue et somme avec un dé déjà écarté.
* Bonus immédiats en chaîne et absence de double attribution.
* Bonus au début des tours.
* Phases passives, recours et fenêtres +1.
* Complément des dés actifs sans effet.
* Scores et renards.
* Fin de partie après toutes les résolutions obligatoires.

Vérifier également :

* Une action refusée laisse l’état inchangé.
* Deux parties sont indépendantes.
* Une commande répétée n’est appliquée qu’une fois.
* Une commande obsolète est refusée.
* L’accès direct au moteur et l’API produisent le même résultat pour un scénario déterministe.
* Plusieurs parties automatiques se terminent légalement.

Pour comparer Python et TypeScript, utiliser des lancers imposés identiques : une même graine ne garantit pas les mêmes tirages entre deux générateurs de langages différents.

Si un navigateur est disponible, vérifier les interactions essentielles après connexion du front. Sinon, préciser les vérifications manuelles restantes.

**13. Documentation et livraison**

Fournir :

* Le moteur Python fonctionnel.
* L’API FastAPI fonctionnelle.
* Le front connecté.
* Les tests.
* Le script de simulation sans HTTP.
* Les dépendances et commandes de lancement.
* Un guide expliquant l’architecture et les limites actuelles.

Documenter les commandes exactes pour lancer le serveur, le front, les tests et une partie automatique.

Terminer par un compte rendu concis indiquant :

* Ce qui a été migré.
* Les vérifications réellement exécutées.
* Les éventuels écarts de règles ou blocages.
* Les étapes nécessaires pour démarrer le projet.

La migration est terminée lorsqu’une partie peut être jouée dans React avec les règles exclusivement exécutées en Python, et lorsque le même moteur peut terminer une partie automatique sans navigateur ni serveur FastAPI.
