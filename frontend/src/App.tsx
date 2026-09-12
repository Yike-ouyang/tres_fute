import { useState } from "react";
import CheckboxCell from "./components/CheckboxCell";
import NumberCell from "./components/NumberCell";
import FixedCell from "./components/FixedCell";
import DieSlot from "./components/DieSlot";
import {
  BLUE_CENTER_INDEX,
  BLUE_CENTER_VALUE,
  BROWN_NUMBERS,
  DIE_IDS,
  DIE_LABELS,
  ROW_NUMBERS,
  type DieColor,
  type DieState,
} from "./boardData";
import "./App.css";

type Checks = Record<string, boolean>;
type Inputs = Record<string, string>;
type Dice = Record<string, DieState>;

function createInitialDice(): Dice {
  const dice: Dice = {};
  for (const id of DIE_IDS) {
    dice[id] = { value: "", color: "" };
  }
  return dice;
}

function App() {
  const [checks, setChecks] = useState<Checks>({});
  const [inputs, setInputs] = useState<Inputs>({});
  const [dice, setDice] = useState<Dice>(createInitialDice);

  const toggleCheck = (id: string) => {
    setChecks((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const setInput = (id: string, value: string) => {
    setInputs((prev) => ({ ...prev, [id]: value }));
  };

  const setDieValue = (id: string, value: number | "") => {
    setDice((prev) => ({ ...prev, [id]: { ...prev[id], value } }));
  };

  const setDieColor = (id: string, color: DieColor | "") => {
    setDice((prev) => ({ ...prev, [id]: { ...prev[id], color } }));
  };

  const rows = <T,>(count: number) =>
    Array.from({ length: count }, (_, i) => i + 1) as T[];

  return (
    <div className="board">
      <h1 className="board-title">Plateau de dés</h1>

      {/* 1. Barre de suivi des tours */}
      <section className="zone zone-turns" aria-label="Barre de suivi des tours">
        <h2 className="zone-title">Tours</h2>
        <div className="turn-bar">
          {rows<number>(6).map((n) => {
            const id = `turn-${n}`;
            return (
              <CheckboxCell
                key={id}
                id={id}
                label={`Tour ${n}`}
                number={n}
                checked={!!checks[id]}
                onToggle={toggleCheck}
              />
            );
          })}
        </div>
      </section>

      {/* Dés (gauche) + Compteurs de bonus (droite) */}
      <div className="dice-and-bonus">
        <section className="zone zone-dice" aria-label="Emplacements de dés">
          <h2 className="zone-title">Dés</h2>
          <div className="dice-row">
            {DIE_IDS.map((id, index) => (
              <DieSlot
                key={id}
                id={id}
                label={DIE_LABELS[index]}
                state={dice[id]}
                onValueChange={setDieValue}
                onColorChange={setDieColor}
              />
            ))}
          </div>
        </section>

        <section className="zone zone-bonus" aria-label="Compteurs de bonus">
          <h2 className="zone-title">Compteurs</h2>
          {["Relance", "Joker", "+1"].map((bar) => (
            <div className="bonus-bar" key={`bonus-${bar}`}>
              <span className="bonus-label">Compteur {bar}</span>
              <div className="bonus-cells">
                {rows<number>(7).map((pos) => {
                  const id = `bonus-${bar}-cell-${pos}`;
                  return (
                    <CheckboxCell
                      key={id}
                      id={id}
                      label={`Compteur ${bar}, case ${pos}`}
                      checked={!!checks[id]}
                      onToggle={toggleCheck}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      </div>

      {/* Zone jaune (gauche) + Zone turquoise (droite) */}
      <div className="grids-row">
        <section className="zone zone-yellow" aria-label="Zone jaune">
          <h2 className="zone-title"></h2>
          <div className="grid grid-6col">
            {rows<number>(3).map((r) =>
              ROW_NUMBERS.map((num, c) => {
                const col = c + 1;
                const id = `yellow-r${r}-c${col}`;
                return (
                  <CheckboxCell
                    key={id}
                    id={id}
                    label={`Jaune ligne ${r} colonne ${col}, nombre ${num}`}
                    number={num}
                    checked={!!checks[id]}
                    onToggle={toggleCheck}
                  />
                );
              })
            )}
          </div>
        </section>

        <section className="zone zone-turquoise" aria-label="Zone turquoise">
          <div className="grid grid-6col">
            {rows<number>(6).map((r) =>
              ROW_NUMBERS.map((num, c) => {
                const col = c + 1;
                const id = `turquoise-r${r}-c${col}`;
                return (
                  <CheckboxCell
                    key={id}
                    id={id}
                    label={`Turquoise ligne ${r} colonne ${col}, nombre ${num}`}
                    number={num}
                    checked={!!checks[id]}
                    onToggle={toggleCheck}
                  />
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* Pistes empilées : bleu foncé, marron, rose */}
      <section className="zone zone-blue" aria-label="Piste bleu foncé">
        <div className="track">
          {rows<number>(11).map((n) => {
            const id = `blue-cell-${n}`;
            if (n === BLUE_CENTER_INDEX) {
              return (
                <FixedCell
                  key={id}
                  id={id}
                  label={`Bleu case ${n}, valeur fixe ${BLUE_CENTER_VALUE}`}
                  value={BLUE_CENTER_VALUE}
                />
              );
            }
            return (
              <NumberCell
                key={id}
                id={id}
                label={`Bleu case ${n}`}
                value={inputs[id] ?? ""}
                onChange={setInput}
              />
            );
          })}
        </div>
      </section>

      <section className="zone zone-brown" aria-label="Piste marron">
        <div className="track">
          {BROWN_NUMBERS.map((num, i) => {
            const n = i + 1;
            const id = `brown-cell-${n}`;
            return (
              <CheckboxCell
                key={id}
                id={id}
                label={`Marron case ${n}, nombre ${num}`}
                number={num}
                checked={!!checks[id]}
                onToggle={toggleCheck}
              />
            );
          })}
        </div>
      </section>

      <section className="zone zone-pink" aria-label="Piste rose">
        <div className="track">
          {rows<number>(12).map((n) => {
            const id = `pink-cell-${n}`;
            return (
              <NumberCell
                key={id}
                id={id}
                label={`Rose case ${n}`}
                value={inputs[id] ?? ""}
                onChange={setInput}
              />
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default App;
