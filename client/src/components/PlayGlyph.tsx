interface PlayGlyphProps {
  isPlaying: boolean;
}

/** Pure geometry, scaled 0.9x as specified. No icon font. */
export function PlayGlyph({ isPlaying }: PlayGlyphProps) {
  if (isPlaying) {
    return (
      <span className="flex gap-[4.5px]" aria-hidden="true">
        <span className="block w-[3.6px] h-[16.2px] bg-paper" />
        <span className="block w-[3.6px] h-[16.2px] bg-paper" />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className="block ml-1"
      style={{
        borderLeft: "14.4px solid var(--color-paper)",
        borderTop: "9px solid transparent",
        borderBottom: "9px solid transparent",
      }}
    />
  );
}
