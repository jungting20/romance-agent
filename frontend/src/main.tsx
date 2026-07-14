import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "@/app/app";
import { QueryProvider } from "@/app/query/query-provider";
import { enableMocking } from "@/mocks/enable-mocking";

import "./index.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element was not found");
}

await enableMocking();

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <QueryProvider>
        <AppRoutes />
      </QueryProvider>
    </BrowserRouter>
  </StrictMode>,
);
