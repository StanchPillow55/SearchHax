import { useState } from "react";
import { Icon } from "../shared";

export interface DemoStep {
  title: string;
  body: string;
  run: () => void;
}

export function DemoGuide({
  steps,
  index,
  setIndex,
  onExit,
}: {
  steps: DemoStep[];
  index: number;
  setIndex: (i: number) => void;
  onExit: () => void;
}) {
  const [min, setMin] = useState(false);
  const step = steps[index];
  const go = (i: number) => {
    setIndex(i);
    steps[i].run();
  };
  if (min)
    return (
      <button className="demo-pill" onClick={() => setMin(false)}>
        <Icon name="play" size={12} /> Guided demo · step {index + 1}/{steps.length}
      </button>
    );
  return (
    <div className="demo-guide" role="dialog" aria-label="Guided prototype journey">
      <div className="demo-head">
        <span>
          <Icon name="spark" size={12} /> Simulated prototype journey · illustrative events
        </span>
        <div>
          <button onClick={() => setMin(true)} title="Minimise">
            <Icon name="minus" size={13} />
          </button>
          <button onClick={onExit} title="Exit demo">
            <Icon name="close" size={13} />
          </button>
        </div>
      </div>
      <div className="demo-steps">
        {steps.map((s, i) => (
          <button key={i} className={`${i === index ? "active" : ""} ${i < index ? "done" : ""}`} onClick={() => go(i)} title={s.title} />
        ))}
      </div>
      <small>
        Step {index + 1} of {steps.length}
      </small>
      <h3>{step.title}</h3>
      <p>{step.body}</p>
      <div className="demo-actions">
        <button disabled={index === 0} onClick={() => go(index - 1)}>
          <Icon name="prev" size={13} /> Back
        </button>
        <button onClick={() => step.run()} title="Re-apply this step">
          <Icon name="history" size={13} /> Replay step
        </button>
        {index < steps.length - 1 ? (
          <button className="primary" onClick={() => go(index + 1)}>
            Next <Icon name="next" size={13} />
          </button>
        ) : (
          <button className="primary" onClick={onExit}>
            Finish <Icon name="check" size={13} />
          </button>
        )}
      </div>
      <em>Everything stays interactive — you can click, scrub and branch yourself at any step.</em>
    </div>
  );
}
