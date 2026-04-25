export interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  steps: Array<{ title: string; optional?: boolean }>;
}

export default function StepIndicator({
  currentStep,
  totalSteps,
  steps,
}: StepIndicatorProps) {
  return (
    <div className="intake-step-indicator">
      <div className="intake-step-progress-bar">
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div
            key={i}
            className={`intake-progress-dot ${
              i < currentStep ? "completed" : i === currentStep - 1 ? "active" : ""
            }`}
            title={steps[i]?.title}
          >
            {i < currentStep ? "✓" : i + 1}
          </div>
        ))}
      </div>
      <div className="intake-step-labels">
        {steps.map((step, i) => (
          <div
            key={i}
            className={`intake-step-label ${
              i === currentStep - 1 ? "active" : i < currentStep - 1 ? "completed" : ""
            }`}
          >
            <span className="intake-step-title">{step.title}</span>
            {step.optional && <span className="intake-step-optional">(Optional)</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
