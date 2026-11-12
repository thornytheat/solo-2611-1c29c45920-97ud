import { useUi, uiStore } from '../../stores/uiStore';

export default function Toasts() {
  const state = useUi();
  if (!state.toasts.length) return null;
  return (
    <div className="toasts" role="status" aria-live="polite">
      {state.toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.tone}`} onClick={() => uiStore.dismiss(toast.id)}>
          {toast.text}
        </div>
      ))}
    </div>
  );
}
