/** 卡点事件分布：末事件聚合（多条路径共享同一个卡点）。 */
import type { ChokePoint } from '../../types/models';
import { num, pct } from '../../utils/format';

export default function ChokeBars({ points }: { points: ChokePoint[] }) {
  if (!points.length) return <div className="loading">该队列没有卡点事件</div>;
  const max = Math.max(...points.map((point) => point.share_pct), 1);
  return (
    <div data-testid="choke-bars">
      {points.map((point, index) => (
        <div className="bar-row" key={point.event}>
          <div style={{ fontSize: '0.86rem' }}>
            <span className="mono tiny muted">{String(index + 1).padStart(2, '0')}</span> {point.label}
          </div>
          <div className="bar-track">
            <div
              className={`bar-fill ${index === 0 ? 'danger' : 'line-b'}`}
              style={{ width: `${Math.max(3, (point.share_pct / max) * 100)}%` }}
            />
          </div>
          <div className="bar-value">
            {pct(point.share_pct)}
            <div className="tiny muted">{num(point.count)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
