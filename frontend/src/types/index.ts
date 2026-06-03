// ── Autenticação ────────────────────────────────────────────────────────────

export type Role = 'admin' | 'magistrado' | 'advogado' | 'analista' | 'cidadao'

export interface Utilizador {
  id: string
  email: string
  nome: string
  role: Role
  permissoes: string[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expira_em: number
  role: Role
}

export interface LoginRequest {
  email: string
  password: string
}

// ── Análise jurídica ─────────────────────────────────────────────────────────

export type TipoProcesso =
  | 'laboral'
  | 'penal'
  | 'civil'
  | 'administrativo'
  | 'familia'
  | 'consumo'
  | 'dados_pessoais'
  | 'outro'

export interface Facto {
  descricao: string
  relevancia: 'alta' | 'media' | 'baixa'
}

export interface NormaIdentificada {
  diploma: string
  artigo: string
  epigrase: string
  excerto: string
  relevancia: number
  fonte: string
}

export interface ArgumentoJuridico {
  posicao: 'acusacao' | 'defesa' | 'neutro'
  argumento: string
  normas_base: string[]
}

export interface AuditInfo {
  timestamp: string
  normas_citadas: number
  fontes_utilizadas: string[]
  modelo: string
  tokens_input: number
  tokens_output: number
  grounded: boolean
}

export interface AnalysisRequest {
  texto: string
  area_juridica?: TipoProcesso
  fontes?: string[]
}

export interface AnalysisResponse {
  caso_id: string
  factos: Facto[]
  qualificacao_juridica: string
  normas: NormaIdentificada[]
  analise: string
  vias_processuais: string[]
  conclusao: string
  contraditorio?: string
  audit: AuditInfo
}

// ── Resultado do reasoning (pipeline interno) ────────────────────────────────

export interface ResultadoReasoning {
  caso_id: string
  tipo_processo: TipoProcesso
  factos: Facto[]
  qualificacao: string
  normas: NormaIdentificada[]
  analise: string
  argumentos_acusacao: { argumento: string; normas_base: string[] }[]
  argumentos_defesa: { argumento: string; normas_base: string[] }[]
  vias_processuais: string[]
  conclusao: string
  grounded: boolean
  citacoes_suspeitas: { diploma: string; artigo: string }[]
  timestamp: string
}

// ── Processos ────────────────────────────────────────────────────────────────

export type EstadoProcesso =
  | 'Apresentação'
  | 'Citação'
  | 'Contestação'
  | 'Instrução'
  | 'Julgamento'
  | 'Sentença'
  | 'Recurso'
  | 'Concluído'

export interface Processo {
  id: string
  numero: string
  tipo: TipoProcesso
  descricao: string
  estado: EstadoProcesso
  data_inicio: string
  data_atualizacao: string
  partes: { autor: string; reu: string }
}

// ── Documentos ───────────────────────────────────────────────────────────────

export type TipoDocumento =
  | 'peticao_inicial'
  | 'contestacao'
  | 'recurso'
  | 'requerimento'
  | 'queixa_crime'
  | 'exposicao'

export interface DocumentoGerado {
  tipo: TipoDocumento
  titulo: string
  conteudo: string
  data_geracao: string
  caso_id: string
  advertencia: string
}

// ── Navegação ────────────────────────────────────────────────────────────────

export interface NavItem {
  id: string
  icon: string
  label: string
  badge?: number
  permissao?: string
}
