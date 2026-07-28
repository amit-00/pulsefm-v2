interface HeaderProps {
  variant: "desktop" | "mobile";
}

/**
 * LOGIN is a static anchor in slices 0-1. Firebase Auth wires it in slice 3,
 * where it becomes LOGOUT for signed-in listeners.
 */
export function Header({ variant }: HeaderProps) {
  const isDesktop = variant === "desktop";

  return (
    <div
      className={`flex items-center justify-between font-mono text-[11px] font-semibold tracking-[0.22em] ${
        isDesktop ? "px-11 pt-[30px]" : "px-7 pt-[26px]"
      }`}
    >
      <span className="flex items-center gap-2">
        <span className="size-1.5 rounded-full bg-accent" />
        <span className="text-ink/45">PULSE FM</span>
      </span>
      <span className="flex items-center gap-[26px]">
        {isDesktop && <span className="text-ink/45">HOW IT WORKS</span>}
        <a
          href="#"
          className="text-ink/45 no-underline tracking-[0.22em] hover:opacity-100"
        >
          LOGIN
        </a>
      </span>
    </div>
  );
}
