// Render an option's visual: a hex color becomes a swatch, everything else
// (emoji today, image URLs tomorrow) renders as large glyph/text.
export function Visual({ visual, size = "text-7xl" }: { visual: string; size?: string }) {
  if (/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(visual)) {
    return (
      <span
        className="inline-block w-24 h-24 rounded-3xl shadow-inner"
        style={{ background: visual }}
        aria-hidden
      />
    );
  }
  return (
    <span className={`${size} leading-none`} aria-hidden>
      {visual}
    </span>
  );
}
