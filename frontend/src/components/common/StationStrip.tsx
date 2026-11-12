/** 漏斗步骤条：地铁线路 + 站点圆圈 + 站名牌 + 换乘（流失）箭头。 */
import type { LostStep, StepResult } from '../../types/models';
import { lineVar } from '../../constants/enums';
import { days, num, pct } from '../../utils/format';

interface Props {
  steps: StepResult[];
  lostSteps?: LostStep[];
  lineColor?: string;
  selectedStep?: number;
  onSelectStep?: (index: number) => void;
}

export default function StationStrip({ steps, lostSteps = [], lineColor = 'line-a', selectedStep, onSelectStep }: Props) {
  const color = lineVar(lineColor);
  return (
    <div className="strip" data-testid="station-strip">
      {steps.map((step, index) => {
        const lost = lostSteps.find((item) => item.index === index);
        const isSelected = selectedStep === step.index;
        return (
          <div
            key={step.index}
            className={`station ${index === 0 ? 'first' : ''} ${index === steps.length - 1 ? 'last' : ''}`}
            style={{ ['--line-color' as string]: color, cursor: onSelectStep ? 'pointer' : 'default' }}
            onClick={() => onSelectStep?.(step.index)}
            data-testid={`station-${step.index}`}
          >
            <div className="station-plate" style={isSelected ? { borderColor: color, color } : undefined}>
              <b>
                {step.index + 1}. {step.label}
              </b>
              <span>{num(step.users)} 人</span>
            </div>
            <div className="station-rail">
              <span className="station-dot" />
            </div>
            <div className="station-meta">
              {index > 0 ? <span style={{ color: 'var(--signal)' }}>较上一步 {pct(step.rate_from_prev)}</span> : <span>进入 {num(step.users)} 人</span>}
              {index > 0 ? <span>P50 {days(step.p50_days)}</span> : <span>窗口起点</span>}
            </div>
            {lost && lost.lost > 0 ? (
              <div className="transfer">
                流失 {num(lost.lost)} 人 · {pct(lost.lost_share)}
              </div>
            ) : (
              <div className="transfer" style={{ color: 'var(--ok)' }}>
                {index === steps.length - 1 ? '链路终点' : '无流失'}
              </div>
            )}
            {index === steps.length - 1 && index < 2 ? null : null}
          </div>
        );
      })}
    </div>
  );
}
