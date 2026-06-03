/**
 * Serviço de API do SNAJI.
 *
 * Toda a comunicação com o backend passa por aqui.
 * O token JWT é injectado automaticamente em cada pedido.
 * Erros 401 fazem logout automático.
 */

import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import type {
  LoginRequest,
  TokenResponse,
  Utilizador,
  AnalysisRequest,
  AnalysisResponse,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

// ── Cliente HTTP base ────────────────────────────────────────────────────────

function criarCliente(): AxiosInstance {
  const cliente = axios.create({
    baseURL: BASE_URL,
    timeout: 30_000,
    headers: { 'Content-Type': 'application/json' },
  })

  // Injecto o token em cada pedido
  cliente.interceptors.request.use((config) => {
    const token = sessionStorage.getItem('snaji_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })

  // Trato erros globais
  cliente.interceptors.response.use(
    (res) => res,
    (error) => {
      if (error.response?.status === 401) {
        // Token expirado ou inválido — limpa sessão
        sessionStorage.removeItem('snaji_token')
        sessionStorage.removeItem('snaji_utilizador')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
  )

  return cliente
}

export const api = criarCliente()

// ── Autenticação ─────────────────────────────────────────────────────────────

export const authService = {
  async login(dados: LoginRequest): Promise<TokenResponse> {
    const res: AxiosResponse<TokenResponse> = await api.post('/auth/login', dados)
    return res.data
  },

  async meusDados(): Promise<Utilizador> {
    const res: AxiosResponse<Utilizador> = await api.get('/auth/me')
    return res.data
  },

  logout(): void {
    sessionStorage.removeItem('snaji_token')
    sessionStorage.removeItem('snaji_utilizador')
  },

  guardarToken(token: string): void {
    sessionStorage.setItem('snaji_token', token)
  },

  tokenGuardado(): string | null {
    return sessionStorage.getItem('snaji_token')
  },
}

// ── Análise jurídica ─────────────────────────────────────────────────────────

export const juridicalService = {
  async analisar(request: AnalysisRequest): Promise<AnalysisResponse> {
    const res: AxiosResponse<AnalysisResponse> = await api.post('/analysis', request)
    return res.data
  },

  async listarFontes(): Promise<{ fontes: { codigo: string; nome: string; artigos: number }[]; total_artigos: number }> {
    const res = await api.get('/fontes')
    return res.data
  },
}

// ── Utilitários ───────────────────────────────────────────────────────────────

export function tratarErroAPI(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).join(', ')
    if (error.response?.status === 503) return 'Serviço temporariamente indisponível.'
    if (error.response?.status === 429) return 'Demasiados pedidos. Aguarde um momento.'
  }
  return 'Erro inesperado. Tente novamente.'
}
