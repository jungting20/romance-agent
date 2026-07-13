import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";

function Bootstrap() {
  return null;
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <Bootstrap />
  </StrictMode>,
);

