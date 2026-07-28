import { useStation } from "./hooks/useStation";
import { Player } from "./components/Player";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export function App() {
  const { snapshot, offsetMs, error } = useStation(API_BASE_URL);

  if (error !== null && snapshot === null) {
    return (
      <div className="grid h-full place-items-center px-8 text-center font-mono text-[11px] tracking-[0.22em] text-ink/45 uppercase">
        Station offline — {error.message}
      </div>
    );
  }

  return <Player snapshot={snapshot} offsetMs={offsetMs} />;
}
