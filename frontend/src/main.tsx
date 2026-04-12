import ReactDOM from "react-dom/client";

import { AppRouter } from "@/app/router";
import { AppProviders } from "@/app/providers";
import "@/index.css";

document.documentElement.classList.add("dark");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <AppProviders>
    <AppRouter />
  </AppProviders>,
);
