import type { ReactNode } from "react";

export interface IconProps {
  size?: number;
  className?: string;
  strokeWidth?: number;
}

function I({
  size = 18,
  className,
  strokeWidth = 1.6,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const PlayIcon = ({ size, className }: IconProps) => (
  <I size={size} className={className} strokeWidth={0}>
    <path d="M8 5.5v13l11-6.5z" fill="currentColor" stroke="none" />
    <circle cx="8" cy="5.5" r="0.01" stroke="none" />
  </I>
);

export const UploadIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M12 15V4m0 0L8 8m4-4l4 4" />
    <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </I>
);

export const FilmIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M3.5 9h3m-3 6h3M17.5 9h3m-3 6h3" />
  </I>
);

export const GridIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="4" y="4" width="7" height="7" rx="1.5" />
    <rect x="13" y="4" width="7" height="7" rx="1.5" />
    <rect x="4" y="13" width="7" height="7" rx="1.5" />
    <rect x="13" y="13" width="7" height="7" rx="1.5" />
  </I>
);

export const ActivityIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M3 12h4l2-7 4 14 2-7h6" />
  </I>
);

export const ReviewIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="3.5" y="6" width="17" height="12" rx="1.5" />
    <path d="M11 9.5v5l4-2.5z" />
  </I>
);

export const CampaignIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M4 11v2l5 4V7l-5 4z" />
    <path d="M9 16v2h2c.3 0 .6 0 .8-.2l1.7-1.3" />
    <path d="M14 6.5c3.4 2.2 3.4 8.8 0 11" />
  </I>
);

export const AutoIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M15.5 3.5l-1.7 4.2 3.5 1.2-2.8 4" />
    <path d="M9 8l-2.4 6 3.9 1.7" />
    <path d="M6.5 20.5c8 1 11-3.5 14-7" />
  </I>
);

export const SettingsIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M4 6h10M17.5 6H20M4 12h3M10.5 12H20M4 18h13M20 18h0" />
    <circle cx="15" cy="6" r="2.5" />
    <circle cx="8" cy="12" r="2.5" />
    <circle cx="18.5" cy="18" r="2.5" />
  </I>
);

export const MonitorIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="3" y="4" width="18" height="13" rx="2" />
    <path d="M8 21h8M12 17v4" />
  </I>
);

export const ExportIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M12 15V4m0 0L8 8m4-4l4 4" />
    <path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" />
  </I>
);

export const TrashIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M4 7h16" />
    <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    <path d="M10 11v6M14 11v6" />
    <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
  </I>
);

export const RetryIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
    <path d="M3 3v5h5" />
  </I>
);

export const CheckIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M5 13l4 4L19 7" />
  </I>
);

export const XIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M6 6l12 12M18 6L6 18" />
  </I>
);

export const ArrowRightIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M5 12h14m-6-6l6 6-6 6" />
  </I>
);

export const ArrowLeftIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M19 12H5m6-6l-6 6 6 6" />
  </I>
);

export const CopyIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
  </I>
);

export const InboxIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M3.5 13.5l3.2 4.2a1 1 0 0 0 .8.4h8.9a1 1 0 0 0 .8-.4l3.2-4.2" />
    <path d="M3.5 13.5V6a1.5 1.5 0 0 1 1.5-1.5h14A1.5 1.5 0 0 1 20.5 6v7.5" />
    <path d="M3.5 13.5H8a1.5 1.5 0 0 0 1.5-1.5v0A1.5 1.5 0 0 1 11 10.5h2a1.5 1.5 0 0 1 1.5 1.5v0a1.5 1.5 0 0 0 1.5 1.5h4.5" />
  </I>
);

export const ZapIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <path d="M13 3L5 13h6l-1 8l8-10h-6z" />
  </I>
);

export const StitchIcon = ({ size, className, strokeWidth }: IconProps) => (
  <I size={size} className={className} strokeWidth={strokeWidth}>
    <rect x="3" y="5" width="8" height="14" rx="1.5" />
    <rect x="13" y="5" width="8" height="14" rx="1.5" />
    <path d="M13 9.5L8 14" />
  </I>
);