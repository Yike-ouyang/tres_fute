import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { installDebugGlobals } from "./game/debug";
import "./index.css";

installDebugGlobals();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
