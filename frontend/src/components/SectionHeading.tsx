import type { ReactNode } from "react";

type SectionHeadingProps = {
    eyebrow: string;
    title: string;
    description: string;
    action?: ReactNode;
};

export function SectionHeading({
    eyebrow,
    title,
    description,
    action,
}: SectionHeadingProps) {
    return (
        <div className="dashboard-section-heading">
            <div>
                <span>{eyebrow}</span>
                <h2>{title}</h2>
                <p>{description}</p>
            </div>
            {action && (
                <div className="dashboard-section-action">{action}</div>
            )}
        </div>
    );
}
