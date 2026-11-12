import type { ReactNode } from 'react';

interface Props {
  eyebrow?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}

export default function EmptyState({ eyebrow = 'EMPTY · 暂无数据', title, hint, action }: Props) {
  return (
    <div className="empty" data-testid="empty-state">
      <div className="eyebrow">{eyebrow}</div>
      <h3>{title}</h3>
      {hint ? <p className="muted" style={{ margin: 0, fontSize: '0.86rem', maxWidth: '52ch' }}>{hint}</p> : null}
      {action}
    </div>
  );
}
