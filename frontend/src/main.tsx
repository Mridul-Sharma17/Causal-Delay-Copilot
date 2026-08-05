import { createRoot } from "react-dom/client";

import App from "./App";
import "@carbon/styles/css/styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Core application root is missing");
}

createRoot(rootElement).render(<App />);
