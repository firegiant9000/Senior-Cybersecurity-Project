import React from 'react';

interface Props {
    variant?: 'chart' | 'stat' | 'map';
}

const WidgetSkeleton: React.FC<Props> = ({ variant = 'chart' }) => {
    if (variant === 'stat') {
        return (
            <div className="skeleton-stat">
                <div className="skeleton-line skeleton-line--short" />
                <div className="skeleton-line skeleton-line--value" />
                <div className="skeleton-line skeleton-line--xs" />
            </div>
        );
    }

    if (variant === 'map') {
        return (
            <div className="skeleton-map">
                <div className="skeleton-block skeleton-block--map" />
            </div>
        );
    }

    // chart (default)
    return (
        <div className="skeleton-chart">
            <div className="skeleton-bars">
                {[65, 90, 45, 75, 55, 80].map((h, i) => (
                    <div
                        key={i}
                        className="skeleton-bar"
                        style={{ height: `${h}%` }}
                    />
                ))}
            </div>
        </div>
    );
};

export default WidgetSkeleton;
