import { useState } from "react";
import type { ReactNode } from "react";

type Props = {
    title: string;
    subtitle?: string;
    defaultOpen?: boolean;
    children: ReactNode;
};

export function CollapsibleSection({
    title,
    subtitle,
    defaultOpen = false,
    children,
}: Props) {
    const [open, setOpen] = useState(defaultOpen);

    return (
        <section className="collapsible-section">
            <button
                className="collapsible-header"
                onClick={() => setOpen(!open)}
            >
                <div>
                    <h2>{title}</h2>

                    {subtitle && (
                        <p>{subtitle}</p>
                    )}
                </div>

                <span
                    className={`collapse-icon ${open ? "open" : ""
                        }`}
                >
                    ▼
                </span>
            </button>

            <div
                className={`collapsible-content ${open ? "expanded" : ""
                    }`}
            >
                {children}
            </div>
        </section>
    );
}