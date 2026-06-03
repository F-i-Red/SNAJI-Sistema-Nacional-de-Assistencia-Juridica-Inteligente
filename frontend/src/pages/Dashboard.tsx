import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../auth/session'
import { api, tratarErroAPI } from '../services/api'

interface MetricaCard {
  label: string
  valor: string
  delta?: string
  tendencia?: 'up' | 'down' | null
  dourado?: boolean
}

interface PrazoItem {
  descricao: string
  data_limite: string
  urgente: boolean
}

interface ProcessoResumo {
  id: string
  numero: string
  tipo: string
  descricao: string
  estado: string
  prazos_urgentes: number
  atualizado_em: string
}

const CORES_TIPO: Record<string, string> = {
  laboral: '#185FA5', penal: '#C0392B', civil: '#BA7517',
  administrativo: '#6B4C9A', familia: '#0F6E56', dados_pessoais: '#0F6E56',
}

const METRICAS_POR_ROLE: Record<string, MetricaCard[]> = {
  cidadao: [
    { label: 'Consultas', valor: '7', delta: '+3 este mês', tendencia: 'up' },
    { label: 'Processos activos', valor: '2', delta: '1 pendente' },
    { label: 'Documentos gerados', valor: '4', delta: '1 em rascunho' },
    { label: 'Poupança estimada', valor: '€ 840', delta: 'vs. honorários', dourado: true },
  ],
  advogado: [
    { label: 'Processos activos', valor: '12', delta: '+2 esta semana', tendencia: 'up' },
    { label: 'Análises hoje', valor: '5', delta: '3 pendentes' },
    { label: 'Peças processuais', valor: '34', delta: 'este mês' },
    { label: 'Taxa de sucesso', valor: '78%', delta: '+4% vs. anterior', tendencia: 'up', dourado: true },
  ],
  magistrado: [
    { label: 'Processos pendentes', valor: '8', delta: '2 urgentes' },
    { label: 'Decisões este mês', valor: '14', delta: '+2 vs. anterior', tendencia: 'up' },
    { label: 'Prazo médio', valor: '23 d', delta: '-4 dias vs. meta', tendencia: 'up', dourado: true },
    { label: 'Conformidade', valor: '100%', delta: 'auditoria ok', tendencia: 'up' },
  ],
  analista: [
    { label: 'Consultas', valor: '23', delta: 'este mês' },
    { label: 'Processos analisados', valor: '18', delta: '+5 esta semana' },
    { label: 'Relatórios', valor: '6', delta: 'este mês' },
    { label: 'Corpus jurídico', valor: '246', delta: 'artigos reais', dourado: true },
  ],
}

export default function PaginaDashboard() {
  const { utilizador } = useAuthStore()
  const navigate = useNavigate()
  const [processos, setProcessos] = useState<ProcessoResumo[]>([])
  const [erro, setErro] = useState<string | null>(null)

  const role = utilizador?.role ?? 'cidadao'
  const metricas = METRICAS_POR_ROLE[role] ?? METRICAS_POR_ROLE.cidadao

  useEffect(() => {
    api.get('/processos')
      .then(r => setProcessos(r.data.processos.slice(0, 3)))
      .catch(e => setErro(tratarErroAPI(e)))
  }, [])

  const primeiroNome = utilizador?.nome.split(' ')[0] ?? ''
  const saudacao = (() => {
    const h = new Date().getHours()
    if (h < 12) return 'Bom dia'
    if (h < 18) return 'Boa tarde'
    return 'Boa noite'
  })()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* Título */}
      <div>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 24, fontWeight: 500,
          color: 'var(--color-text-primary)',
        }}>
          {saudacao}, {primeiroNome}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', marginTop: 3 }}>
          {new Date().toLocaleDateString('pt-PT', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Métricas */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        {metricas.map(m => (
          <div key={m.label} style={{
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-lg)',
            padding: '14px 16px',
          }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 6 }}>
              {m.label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 500, color: m.dourado ? '#c4960a' : 'var(--color-text-primary)' }}>
              {m.valor}
            </div>
            {m.delta && (
              <div style={{
                fontSize: 11, marginTop: 3,
                color: m.tendencia === 'up' ? 'var(--color-text-success)'
                     : m.tendencia === 'down' ? 'var(--color-text-danger)'
                     : 'var(--color-text-tertiary)',
              }}>
                {m.tendencia === 'up' ? '↑ ' : m.tendencia === 'down' ? '↓ ' : ''}{m.delta}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Linha inferior */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>

        {/* Processos recentes */}
        <div style={{
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-lg)',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '10px 14px',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>
              Processos recentes
            </span>
            <button onClick={() => navigate('/processos')} style={{
              background: 'none', border: 'none', fontSize: 11,
              color: 'var(--color-text-secondary)', cursor: 'pointer',
              textDecoration: 'underline', textUnderlineOffset: 3, fontFamily: 'inherit',
            }}>
              Ver todos
            </button>
          </div>
          <div style={{ padding: '0 14px' }}>
            {processos.length === 0 && !erro && (
              <div style={{ padding: '1rem 0', fontSize: 13, color: 'var(--color-text-tertiary)', textAlign: 'center' }}>
                Nenhum processo ainda
              </div>
            )}
            {processos.map(p => (
              <div key={p.id} onClick={() => navigate(`/processos`)} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '10px 0',
                borderBottom: '0.5px solid var(--color-border-tertiary)',
                cursor: 'pointer',
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 4,
                  background: CORES_TIPO[p.tipo] ?? 'var(--color-text-tertiary)',
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {p.descricao}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>
                    {p.numero} · {p.estado}
                  </div>
                </div>
                {p.prazos_urgentes > 0 && (
                  <span style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 10,
                    background: 'var(--color-background-danger)',
                    color: 'var(--color-text-danger)', fontWeight: 500, flexShrink: 0,
                  }}>
                    {p.prazos_urgentes} urgente{p.prazos_urgentes > 1 ? 's' : ''}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Acesso rápido */}
        <div style={{
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-lg)',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
            <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>
              Acesso rápido
            </span>
          </div>
          <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { icon: 'ti-message-question', label: 'Nova consulta jurídica', path: '/consulta', destaque: true },
              { icon: 'ti-folder-plus', label: 'Abrir novo processo', path: '/processos' },
              { icon: 'ti-file-plus', label: 'Gerar documento', path: '/documentos' },
              ...(role === 'magistrado' || role === 'advogado'
                ? [{ icon: 'ti-shield-check', label: 'Ver auditoria', path: '/auditoria' }]
                : []
              ),
            ].map(item => (
              <button key={item.path} onClick={() => navigate(item.path)} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px',
                background: item.destaque ? '#0a2342' : 'var(--color-background-secondary)',
                border: item.destaque ? 'none' : '0.5px solid var(--color-border-tertiary)',
                borderRadius: 'var(--border-radius-md)',
                cursor: 'pointer', fontFamily: 'inherit',
                color: item.destaque ? '#fff' : 'var(--color-text-primary)',
                fontSize: 13, fontWeight: item.destaque ? 500 : 400,
                textAlign: 'left', transition: 'all 0.15s',
              }}>
                <i className={`ti ${item.icon}`} aria-hidden="true" style={{ fontSize: 16, opacity: 0.8 }} />
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Aviso corpus */}
      <div style={{
        background: 'var(--color-background-info)',
        border: '0.5px solid var(--color-border-info)',
        borderRadius: 'var(--border-radius-md)',
        padding: '10px 14px',
        fontSize: 12, color: 'var(--color-text-info)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <i className="ti ti-info-circle" aria-hidden="true" style={{ fontSize: 15, flexShrink: 0 }} />
        <span>
          Motor jurídico activo · <strong>246 artigos reais</strong> de 6 diplomas portugueses
          (CRP, CT, CC, RGPD, CP, CPC+CPP) · LLM: modo demonstração (sem chave API)
        </span>
      </div>
    </div>
  )
}
