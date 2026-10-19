import type { SVGProps } from "react";

// Functional icons only (controls and sort/state markers). Drawn for this project on a
// 16px grid: 1.5px stroke, square caps and miter joins, no fills.
type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export const Search = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2.75" y="2.75" width="7.5" height="7.5" />
    <path d="M10.5 10.5 14 14" />
  </Svg>
);
export const X = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 3.5 12.5 12.5M12.5 3.5 3.5 12.5" />
  </Svg>
);
export const Check = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 8.5 6.5 12 13 4.5" />
  </Svg>
);
export const ChevronDown = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 6 8 10.5 12.5 6" />
  </Svg>
);
export const ChevronLeft = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 3.5 5.5 8 10 12.5" />
  </Svg>
);
export const ChevronRight = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3.5 10.5 8 6 12.5" />
  </Svg>
);
export const Menu = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
  </Svg>
);
export const Copy = (p: IconProps) => (
  <Svg {...p}>
    <rect x="5.5" y="5.5" width="8" height="8" />
    <path d="M10.5 5.5v-3h-8v8h3" />
  </Svg>
);
export const ArrowLeft = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13 8H3M7 4 3 8l4 4" />
  </Svg>
);
export const ArrowRight = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 8h10M9 4l4 4-4 4" />
  </Svg>
);
export const ArrowUp = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 13V3M4 7l4-4 4 4" />
  </Svg>
);
export const ArrowDown = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 3v10M4 9l4 4 4-4" />
  </Svg>
);
export const Refresh = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13 8a5 5 0 1 1-1.5-3.5M13 2.5v3h-3" />
  </Svg>
);
export const Download = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10" />
  </Svg>
);
export const Upload = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 10.5v-8M4.5 6 8 2.5 11.5 6M3 13.5h10" />
  </Svg>
);
export const Eye = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z" />
    <rect x="6.25" y="6.25" width="3.5" height="3.5" />
  </Svg>
);
export const EyeOff = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z" />
    <path d="M2.5 13.5 13.5 2.5" />
  </Svg>
);
export const Plus = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 3v10M3 8h10" />
  </Svg>
);

/** Busy indicator: a square-ended arc that turns. */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={`animate-spin ${className ?? ""}`}
      role="status"
      aria-label="Loading"
    >
      <path d="M8 2a6 6 0 1 0 6 6" />
    </svg>
  );
}
