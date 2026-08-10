import { useEffect, useState } from "react";
import Dashboard from "./adult/Dashboard";
import ParentView from "./adult/ParentView";
import ChildHome from "./child/ChildHome";
import { t } from "./i18n";
import type { Lang } from "./types";

type Mode = "child" | "adult";
type AdultView = "progress" | "parent";

export default function App() {
  const [lang, setLang] = useState<Lang>("ar");
  const [mode, setMode] = useState<Mode>("child");
  const [adultView, setAdultView] = useState<AdultView>("progress");
  const s = t[lang];

  // Keep document direction in sync so both RTL and LTR lay out correctly.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top chrome — only for the adult; kept minimal in child mode */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-stone-200/70 bg-[var(--paper)]">
        <div className="flex items-center gap-3">
          <span className="text-3xl" aria-hidden>
            🧸
          </span>
          <div>
            <div className="text-xl font-bold leading-none">{s.appName}</div>
            <div className="text-xs text-stone-500">{s.tagline}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-full bg-white shadow-sm p-1">
            <button
              onClick={() => setMode("child")}
              className={[
                "px-4 py-1.5 rounded-full text-sm font-semibold",
                mode === "child" ? "bg-amber-400" : "text-stone-500",
              ].join(" ")}
            >
              {s.childMode}
            </button>
            <button
              onClick={() => setMode("adult")}
              className={[
                "px-4 py-1.5 rounded-full text-sm font-semibold",
                mode === "adult" ? "bg-stone-800 text-white" : "text-stone-500",
              ].join(" ")}
            >
              {s.adultMode}
            </button>
          </div>
          <button
            onClick={() => setLang(lang === "ar" ? "en" : "ar")}
            className="px-4 py-1.5 rounded-full bg-white shadow-sm text-sm font-semibold hover:bg-stone-100"
          >
            {s.switchLang}
          </button>
        </div>
      </header>

      <main className="flex-1">
        {mode === "adult" && (
          <div className="flex justify-center pt-4">
            <div className="flex rounded-full bg-white shadow-sm p-1">
              <button
                onClick={() => setAdultView("progress")}
                className={[
                  "px-4 py-1.5 rounded-full text-sm font-semibold",
                  adultView === "progress"
                    ? "bg-stone-800 text-white"
                    : "text-stone-500 hover:bg-stone-100",
                ].join(" ")}
              >
                {s.progressTab}
              </button>
              <button
                onClick={() => setAdultView("parent")}
                className={[
                  "px-4 py-1.5 rounded-full text-sm font-semibold",
                  adultView === "parent"
                    ? "bg-stone-800 text-white"
                    : "text-stone-500 hover:bg-stone-100",
                ].join(" ")}
              >
                {s.parentView}
              </button>
            </div>
          </div>
        )}
        {mode === "child" ? (
          <ChildHome lang={lang} />
        ) : adultView === "parent" ? (
          <ParentView lang={lang} />
        ) : (
          <Dashboard lang={lang} />
        )}
      </main>
    </div>
  );
}
