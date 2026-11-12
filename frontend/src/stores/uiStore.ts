/** 轻量 UI store：toast 队列 + 当前选中的漏斗（跨页面共享）。 */
import { useSyncExternalStore } from 'react';

export interface Toast {
  id: number;
  text: string;
  tone: 'info' | 'ok' | 'warn';
}

interface UiState {
  toasts: Toast[];
  funnelId: number | null;
  runId: number | null;
}

type Listener = () => void;

class UiStore {
  private state: UiState = { toasts: [], funnelId: null, runId: null };
  private listeners = new Set<Listener>();
  private seq = 1;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getState = (): UiState => this.state;

  private emit(next: Partial<UiState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((listener) => listener());
  }

  toast(text: string, tone: Toast['tone'] = 'info') {
    const toast: Toast = { id: this.seq++, text, tone };
    this.emit({ toasts: [...this.state.toasts, toast] });
    window.setTimeout(() => this.dismiss(toast.id), 3200);
  }

  dismiss(id: number) {
    this.emit({ toasts: this.state.toasts.filter((toast) => toast.id !== id) });
  }

  selectFunnel(funnelId: number) {
    this.emit({ funnelId });
  }

  selectRun(runId: number) {
    this.emit({ runId });
  }
}

export const uiStore = new UiStore();

export function useUi() {
  return useSyncExternalStore(uiStore.subscribe, uiStore.getState);
}
