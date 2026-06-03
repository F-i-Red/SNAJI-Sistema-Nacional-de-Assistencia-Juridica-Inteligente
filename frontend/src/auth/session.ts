/**
 * Store de autenticação do SNAJI.
 * Usa Zustand — gestão de estado simples e sem boilerplate.
 *
 * O estado de sessão é mantido em memória (Zustand) e
 * o token é persistido em sessionStorage (limpa ao fechar o browser).
 * Nunca usamos localStorage para tokens — é menos seguro.
 */

import { create } from 'zustand'
import type { Utilizador, Role } from '../types'
import { authService, tratarErroAPI } from '../services/api'

interface AuthState {
  utilizador: Utilizador | null
  token: string | null
  carregando: boolean
  erro: string | null

  // Acções
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  restaurarSessao: () => Promise<void>
  limparErro: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  utilizador: null,
  token: authService.tokenGuardado(),
  carregando: false,
  erro: null,

  login: async (email, password) => {
    set({ carregando: true, erro: null })
    try {
      const tokenRes = await authService.login({ email, password })
      authService.guardarToken(tokenRes.access_token)
      const utilizador = await authService.meusDados()
      set({ token: tokenRes.access_token, utilizador, carregando: false })
      return true
    } catch (e) {
      set({ erro: tratarErroAPI(e), carregando: false, token: null, utilizador: null })
      return false
    }
  },

  logout: () => {
    authService.logout()
    set({ utilizador: null, token: null, erro: null })
  },

  restaurarSessao: async () => {
    const token = authService.tokenGuardado()
    if (!token) return
    set({ carregando: true })
    try {
      const utilizador = await authService.meusDados()
      set({ utilizador, token, carregando: false })
    } catch {
      // Token expirado — limpa sessão silenciosamente
      authService.logout()
      set({ utilizador: null, token: null, carregando: false })
    }
  },

  limparErro: () => set({ erro: null }),
}))

// ── Hooks de conveniência ────────────────────────────────────────────────────

export function useRole(): Role | null {
  return useAuthStore((s) => s.utilizador?.role ?? null)
}

export function usePodeVer(permissao: string): boolean {
  const utilizador = useAuthStore((s) => s.utilizador)
  if (!utilizador) return false
  return utilizador.permissoes.includes(permissao) || utilizador.permissoes.includes('*')
}
