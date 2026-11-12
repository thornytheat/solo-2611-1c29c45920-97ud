/** 把后端的 {code,message} 翻成一句话，403 单独提示角色边界。 */
import { ApiError } from '../api/client';
import { ROLE_LABELS } from '../constants/roles';
import type { Role } from '../types/models';

export function errorMessage(error: unknown, role?: Role): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      const who = role ? ROLE_LABELS[role] : '当前角色';
      return `403 · ${who}没有这个操作权限（后端已拦截，不是按钮隐藏）`;
    }
    if (error.status === 401) return '登录态已失效，请重新登录';
    if (error.status === 429) return '请求太频繁，稍等几秒再试';
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return '未知错误';
}
