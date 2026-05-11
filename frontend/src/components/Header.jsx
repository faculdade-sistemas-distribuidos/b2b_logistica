export default function Header({ dark, setDark, health }) {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-lg transition-colors dark:border-slate-700/50 dark:bg-slate-900/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-400 shadow-md shadow-brand-400/25">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path d="M8 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM15 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
              <path d="M3 4a1 1 0 00-1 1v10a1 1 0 001 1h1.05a2.5 2.5 0 014.9 0H10a1 1 0 001-1v-5h2.05a2.5 2.5 0 014.9 0H19a1 1 0 001-1v-2a1 1 0 00-.293-.707l-3-3A1 1 0 0016 3h-3a1 1 0 00-1 1v4H4V5a1 1 0 00-1-1z" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-gray-900 dark:text-white sm:text-lg">
              Logística<span className="text-brand-400"> Dashboard</span>
            </h1>
            <p className="hidden text-[10px] font-medium uppercase tracking-widest text-gray-400 sm:block dark:text-gray-500">
              Portal B2B — Equipe 8
            </p>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-3">
          {/* Health */}
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium dark:border-slate-700">
            <span
              className={`h-2 w-2 rounded-full ${
                health === null
                  ? "bg-gray-300 dark:bg-slate-600"
                  : health
                  ? "bg-emerald-400 animate-pulse-slow"
                  : "bg-red-400"
              }`}
            />
            <span className="text-gray-600 dark:text-gray-300">
              {health === null ? "..." : health ? "API Online" : "API Offline"}
            </span>
          </div>

          {/* Theme toggle */}
          <button
            onClick={() => setDark(!dark)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 text-gray-500 transition-colors hover:bg-gray-100 dark:border-slate-700 dark:text-gray-400 dark:hover:bg-slate-800"
            aria-label="Alternar tema"
          >
            {dark ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
