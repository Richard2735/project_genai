import { Chat } from "./components/chat";

export default function Home() {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
            IA
          </div>
          <div>
            <h1 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Agente IA Corporativo
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              RAG + LangChain + Gemini 2.5 Flash
            </p>
          </div>
        </div>
      </header>

      {/* Chat */}
      <Chat />
    </div>
  );
}
