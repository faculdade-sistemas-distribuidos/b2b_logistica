import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { bootstrapAuthToken } from "./api.js";
import "./index.css";

// Le ?jwt=<token> da URL (se vier do portal pai), grava em sessionStorage
// e remove da URL. Tem que rodar ANTES do render pra que a primeira request
// (ex: health/listar) ja saia com Authorization: Bearer <token>.
bootstrapAuthToken();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
