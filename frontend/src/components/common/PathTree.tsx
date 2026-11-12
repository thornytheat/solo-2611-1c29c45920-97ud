/** 前缀树 SVG：地铁风格折线连接 + 站点圆圈 + 站名牌（标签在站点上方，不与线路重叠）。深度 ≤6。 */
import type { TreeNode } from '../../types/models';
import { num } from '../../utils/format';

interface Laid {
  node: TreeNode;
  x: number;
  y: number;
  depth: number;
}

const X_GAP = 158;
const Y_GAP = 50;
const COLORS = ['var(--line-a)', 'var(--line-b)', 'var(--line-c)', 'var(--line-d)', 'var(--signal)'];

export default function PathTree({ tree, total }: { tree: TreeNode; total: number }) {
  if (!tree || !tree.children?.length) {
    return <div className="loading">还没有可展开的路径</div>;
  }

  const nodes: Laid[] = [];
  let leaf = 0;

  function walk(node: TreeNode, depth: number): number {
    const x = 28 + depth * X_GAP;
    let y: number;
    if (!node.children.length) {
      y = 34 + leaf * Y_GAP;
      leaf += 1;
    } else {
      const childYs = node.children.map((child) => walk(child, depth + 1));
      y = (childYs[0] + childYs[childYs.length - 1]) / 2;
    }
    nodes.push({ node, x, y, depth });
    return y;
  }

  tree.children.forEach((child) => walk(child, 0));

  const leaves = Math.max(leaf, 1);
  const height = 46 + leaves * Y_GAP;
  const depthMax = Math.max(...nodes.map((item) => item.depth));
  const width = 28 + (depthMax + 1) * X_GAP + 78;

  return (
    <div className="tree-wrap" data-testid="path-tree">
      <svg className="tree-svg" width={width} height={height} role="img" aria-label="流失前缀树">
        {nodes.map((parent) =>
          parent.node.children.map((child) => {
            const target = nodes.find((item) => item.node === child);
            if (!target) return null;
            const midX = parent.x + X_GAP * 0.5;
            const color = COLORS[Math.min(target.depth, COLORS.length - 1)];
            return (
              <path
                key={`${parent.x}-${parent.y}-${target.x}-${target.y}-${child.label}`}
                d={`M ${parent.x + 7} ${parent.y} H ${midX} V ${target.y} H ${target.x - 7}`}
                fill="none"
                stroke={color}
                strokeWidth={2.2}
                strokeLinecap="round"
                opacity={0.8}
              />
            );
          }),
        )}
        {nodes.map((item, index) => {
          const color = COLORS[Math.min(item.depth, COLORS.length - 1)];
          const share = total ? (item.node.count / total) * 100 : 0;
          return (
            <g key={`${item.x}-${item.y}-${index}`}>
              <circle cx={item.x} cy={item.y} r={7} fill="var(--ink-900)" stroke={color} strokeWidth={3.2} />
              <text x={item.x} y={item.y - 21} textAnchor="middle" className="node-label">
                {item.node.label}
              </text>
              <text x={item.x} y={item.y - 8} textAnchor="middle" className="node-count">
                {num(item.node.count)} · {share.toFixed(1)}%
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
