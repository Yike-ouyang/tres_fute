# Structure
- api/ : contient le squelette du back
- game_engine/ : contient les règles
- simulation/ : système d'avance du jeu
- tests/ : test à la fin de la construction

## API

- __init__.py: initialiser en appelant app.py
- app.py: déclare toutes les apis et les lit aux fonctions
- schemas.py: créer des classes via pydantic pour préciser le format des requetes transitant par app
- store.py: définit la classe store pour conserver les données le temps d'un lancement

## game_engine

- bonuses.py: définit l'emplacement de tous les bonus, la classe "BonusSlot", et les fonctions d'activation des bonus ainsi que les compteurs de bonus. Les effets sont stockés sous la forme d'un dictionnaire "BonusEffect"
- engine.py: crée la classe "GameEngine"
- legal.py: basé sur deux types de data: state et phase= state["phase"]. En utilisant des if, détermine les selections possibles

Cas prévu pour state:
- bonus resolution
- selection
- joker pending
- pink choice

Cas prévu pour phase:
- game over
- fill-slots
- plus1
- passive
- active

- reducer.py: contient toutes les fonctions auxiliaires et le coeur du travail (update le plateau après sélection d'un dé...), fichier de code le plus long
- rules.py: contient les fonctions support de legal.py
- score.py: calcule le score
- serialize.py: transforme les outputs du game engine en json
- types.py: contient toutes les définitions de classes (dés, states, sélection, autre joueur...)