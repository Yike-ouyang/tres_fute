import { useState } from "react";
import ReplayView from "./components/ReplayView";
import PlayView from "./components/PlayView";
import "./App.css";

type View = "replay" | "play" | "ai";

function App() {
  const [view, setView] = useState<View>("play");

  const viewTabs = (
    <nav className="view-tabs" aria-label="Choix de la vue">
      <button
        type="button"
        className={`btn btn-tab${view === "replay" ? " is-active" : ""}`}
        onClick={() => setView("replay")}
      >
        Replay
      </button>
      <button
        type="button"
        className={`btn btn-tab${view === "play" ? " is-active" : ""}`}
        onClick={() => setView("play")}
      >
        Play
      </button>
      <button
        type="button"
        className={`btn btn-tab${view === "ai" ? " is-active" : ""}`}
        onClick={() => setView("ai")}
      >
        Play against AI
      </button>
    </nav>
  );

  return (
    <div className="board">
      <h1 className="board-title">Plateau de dés — Duel à deux joueurs</h1>
      {viewTabs}
      {view === "replay" ? (
        <ReplayView />
      ) : (
        <PlayView key={view} mode={view === "ai" ? "ai" : "human"} onOpenReplay={() => setView("replay")} />
      )}
    </div>
  );
}

export default App;
