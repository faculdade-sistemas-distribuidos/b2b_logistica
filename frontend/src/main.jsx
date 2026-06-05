import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { bootstrapAuthToken } from "./api.js";
import "./index.css";

// Lê ?jwt=<token> da URL (se vier do portal pai), grava em sessionStorage
// e remove da URL. Deve rodar ANTES do render para que a primeira requisição
// (health/listar) já saia com Authorization: Bearer <token>.
bootstrapAuthToken();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
