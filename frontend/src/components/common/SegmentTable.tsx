/** 渠道 × 设备流失率对比表：高亮最大差值分群。 */
import type { SegmentBlock } from '../../types/models';
import { num, pct, pp, signedClass } from '../../utils/format';

interface Props {
  block: SegmentBlock;
  showChannelRollup?: boolean;
  compact?: boolean;
}

export default function SegmentTable({ block, showChannelRollup = true, compact = false }: Props) {
  const topKey = block.top_segment ? `${block.top_segment.channel}-${block.top_segment.device}` : '';
  const maxRate = Math.max(1, ...block.rows.map((row) => row.drop_rate));
  return (
    <div data-testid="segment-table">
      <div className="tiny muted" style={{ marginBottom: 8 }}>
        基期：「{block.from_label} → {block.step_label}」，整体流失率 {pct(block.overall_drop_rate)}，
        最大差值 <b className="mono" style={{ color: 'var(--danger)' }}>{pp(block.max_gap_pp)}</b>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>渠道</th>
            <th>设备</th>
            <th className="num-cell">进入</th>
            <th className="num-cell">流失</th>
            <th className="num-cell">流失率</th>
            <th style={{ width: '26%' }}>分布</th>
            <th className="num-cell">较整体</th>
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row) => {
            const key = `${row.channel}-${row.device}`;
            const isTop = key === topKey;
            return (
              <tr key={key} style={isTop ? { background: 'oklch(0.26 0.05 26 / 0.45)' } : undefined}>
                <td>{row.channel_label}</td>
                <td className="mono">{row.device_label}</td>
                <td className="num-cell">{num(row.users)}</td>
                <td className="num-cell">{num(row.dropped)}</td>
                <td className="num-cell">{pct(row.drop_rate)}</td>
                <td>
                  <div className="bar-track">
                    <div
                      className={`bar-fill ${isTop ? 'danger' : 'line-b'}`}
                      style={{ width: `${Math.max(4, (row.drop_rate / maxRate) * 100)}%` }}
                    />
                  </div>
                </td>
                <td className={`num-cell ${signedClass(row.gap_pp)}`}>{pp(row.gap_pp)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {showChannelRollup ? (
        <div style={{ marginTop: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>
            渠道汇总
          </div>
          {compact ? (
            <div className="tiny muted">
              {block.channel_rows.map((row) => `${row.channel_label} ${pct(row.drop_rate)}`).join(' · ')}
            </div>
          ) : (
            <table className="table">
              <tbody>
                {block.channel_rows.map((row) => (
                  <tr key={row.channel}>
                    <td>{row.channel_label}</td>
                    <td className="num-cell">{num(row.users)} 人</td>
                    <td className="num-cell">{pct(row.drop_rate)}</td>
                    <td className={`num-cell ${signedClass(row.gap_pp)}`}>{pp(row.gap_pp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}
    </div>
  );
}
