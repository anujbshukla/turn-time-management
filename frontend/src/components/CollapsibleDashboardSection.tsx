import {
  useId,
  useState,
} from "react";

import type {
  ReactNode,
} from "react";

type CollapsibleDashboardSectionProps = {
  title: string;
  description: string;
  eyebrow?: string;
  summary?: string;
  status?: string;
  defaultOpen?: boolean;
  children: ReactNode;
};

export function CollapsibleDashboardSection({
  title,
  description,
  eyebrow,
  summary,
  status,
  defaultOpen = false,
  children,
}: CollapsibleDashboardSectionProps) {
  const [isOpen, setIsOpen] =
    useState(defaultOpen);

  const contentId = useId();

  return (
    <section
      className={`dashboard-collapsible ${
        isOpen ? "is-open" : "is-closed"
      }`}
    >
      <button
        type="button"
        className="dashboard-collapsible-trigger"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() =>
          setIsOpen((current) => !current)
        }
      >
        <div className="dashboard-collapsible-copy">
          {eyebrow && (
            <span className="dashboard-collapsible-eyebrow">
              {eyebrow}
            </span>
          )}

          <div className="dashboard-collapsible-title-row">
            <h2>{title}</h2>

            {status && (
              <span className="dashboard-collapsible-status">
                {status}
              </span>
            )}
          </div>

          <p>{description}</p>

          {summary && (
            <span className="dashboard-collapsible-summary">
              {summary}
            </span>
          )}
        </div>

        <span
          className="dashboard-collapsible-chevron"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 20 20"
            focusable="false"
          >
            <path
              d="m5.5 7.5 4.5 4.5 4.5-4.5"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.8"
            />
          </svg>
        </span>
      </button>

      <div
        id={contentId}
        className="dashboard-collapsible-content"
        aria-hidden={!isOpen}
      >
        <div className="dashboard-collapsible-content-inner">
          {children}
        </div>
      </div>
    </section>
  );
}
