import React from 'react';

interface Props {
    title?: string;
    children: React.ReactNode;
}

interface State {
    error: Error | null;
}

class WidgetErrorBoundary extends React.Component<Props, State> {
    state: State = { error: null };

    static getDerivedStateFromError(error: Error): State {
        return { error };
    }

    render() {
        if (this.state.error) {
            return (
                <div className="widget-error-fallback">
                    <span className="widget-error-icon">⚠</span>
                    <span className="widget-error-msg">
                        {this.props.title ?? 'Widget'} failed to load
                    </span>
                    <button
                        className="widget-error-retry"
                        onClick={() => this.setState({ error: null })}
                    >
                        Retry
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

export default WidgetErrorBoundary;
