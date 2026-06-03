import { useEffect, useState } from 'react'
import { api, tratarErroAPI } from '../services/api'
import { useAuthStore } from '../auth/session'

const FASES = ['Apresentação','Citação','Contestação','Instrução','Julgamento','Sentença','Recurso','Concluído']

const CORES: Record<string, string> = {
  laboral: '#185FA5', penal: '#C0392B', civil: '#BA7517',
  administrativo: '#6B4C9A', familia: '#0F6E56', dados_pessoais: '#0F6E56',
}

interface Processo {
  id: string; numero: string; tipo: string; descricao: string
  estado: string; estado_index: number; proximo_estado: string | null
  partes: { nome: string; papel: string }[]
  tribunal: string; comarca: string; valor_causa: number | null
  criado_em: string; atualizado_em: string
  prazos: { descricao: string; data_limite: string; urgente: boolean; cumprido: boolean }[]
  eventos: { timestamp: string; tipo: string; descricao: string; estado_anterior: string | null; estado_novo: string | null }[]
  notas: string[]
  prazos_urgentes?: number
  num_eventos?: number
}

export default function PaginaProcessos() {
  const { utilizador } = useAuthStore()
  const [lista, setLista] = useState<Processo[]>([])
  const [seleccionado, setSeleccionado] = useState<Processo | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [filtroTipo, setFiltroTipo] = useState<string>('todos')
  const [mostrarFormNovo, setMostrarFormNovo] = useState(false)
  const [formNovo, setFormNovo] = useState({ tipo: 'laboral', descricao: '', nome_autor: '', nome_reu: '', comarca: 'Lisboa' })
  const [criando, setCriando] = useState(false)

  const carregar = () => {
    setCarregando(true)
    api.get('/processos')
      .then(r => { setLista(r.data.processos); setCarregando(false) })
      .catch(e => { setErro(tratarErroAPI(e)); setCarregando(false) })
  }

  useEffect(() => { carregar() }, [])

  const verDetalhe = async (id: string) => {
    try {
      const r = await api.get(`/processos/${id}`)
      setSeleccionado(r.data)
    } catch (e) {
      setErro(tratarErroAPI(e))
    }
  }

  const avancar = async (pid: string) => {
    try {
      const fd = new FormData(); fd.append('nota', '')
      await api.post(`/processos/${pid}/avancar`, fd)
      await verDetalhe(pid)
      carregar()
    } catch (e) { setErro(tratarErroAPI(e)) }
  }

  const criarProcesso = async () => {
    if (!formNovo.descricao || !formNovo.nome_autor || !formNovo.nome_reu) return
    setCriando(true)
    try {
      await api.post('/processos', formNovo)
      setMostrarFormNovo(false)
      setFormNovo({ tipo: 'laboral', descricao: '', nome_autor: '', nome_reu: '', comarca: 'Lisboa' })
      carregar()
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCriando(false) }
  }

  const tiposUnicos = ['todos', ...new Set(lista.map(p => p.tipo))]
  const listaFiltrada = filtroTipo === 'todos' ? lista : lista.filter(p => p.tipo === filtroTipo)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          {utilizador?.role === 'magistrado' ? 'Processos em carteira' : utilizador?.role === 'advogado' ? 'Carteira de processos' : 'Os meus processos'}
        </h1>
        <button onClick={() => setMostrarFormNovo(true)} style={{
          padding: '6px 14px', background: '#0a2342', color: '#fff',
          border: 'none', borderRadius: 'var(--border-radius-md)',
          fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          <i className="ti ti-plus" aria-hidden="true" /> Novo processo
        </button>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {tiposUnicos.map(t => (
          <button key={t} onClick={() => setFiltroTipo(t)} style={{
            padding: '4px 12px', borderRadius: 20, fontSize: 11, fontWeight: 500,
            cursor: 'pointer', fontFamily: 'inherit', border: '0.5px solid',
            borderColor: filtroTipo === t ? '#0a2342' : 'var(--color-border-secondary)',
            background: filtroTipo === t ? '#0a2342' : 'var(--color-background-primary)',
            color: filtroTipo === t ? '#fff' : 'var(--color-text-secondary)',
          }}>
            {t}
          </button>
        ))}
      </div>

      {/* Erro */}
      {erro && <div style={{ padding: '8px 12px', background: 'var(--color-background-danger)', border: '0.5px solid var(--color-border-danger)', borderRadius: 'var(--border-radius-md)', fontSize: 13, color: 'var(--color-text-danger)' }}>{erro}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: seleccionado ? '1fr 1.4fr' : '1fr', gap: 10 }}>

        {/* Lista */}
        <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
          {carregando ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13 }}>A carregar...</div>
          ) : listaFiltrada.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13 }}>Nenhum processo encontrado</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Nº processo','Tipo','Descrição','Estado','Prazos',''].map(h => (
                    <th key={h} style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, textAlign: 'left', padding: '8px 10px', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {listaFiltrada.map(p => (
                  <tr key={p.id} style={{ cursor: 'pointer', background: seleccionado?.id === p.id ? 'var(--color-background-secondary)' : 'transparent' }} onClick={() => verDetalhe(p.id)}>
                    <td style={{ padding: '9px 10px', fontFamily: 'monospace', fontSize: 11 }}>{p.numero}</td>
                    <td style={{ padding: '9px 10px' }}>
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, fontWeight: 500, background: `${CORES[p.tipo]}15`, color: CORES[p.tipo] ?? 'var(--color-text-secondary)' }}>
                        {p.tipo}
                      </span>
                    </td>
                    <td style={{ padding: '9px 10px', color: 'var(--color-text-primary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.descricao}</td>
                    <td style={{ padding: '9px 10px', color: 'var(--color-text-secondary)', fontSize: 12, whiteSpace: 'nowrap' }}>{p.estado}</td>
                    <td style={{ padding: '9px 10px' }}>
                      {(p.prazos_urgentes ?? 0) > 0 && (
                        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--color-background-danger)', color: 'var(--color-text-danger)', fontWeight: 500 }}>
                          {p.prazos_urgentes}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '9px 10px' }}>
                      <i className="ti ti-chevron-right" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-tertiary)' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detalhe */}
        {seleccionado && (
          <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', flex: 1 }}>
                {seleccionado.numero}
              </span>
              {seleccionado.proximo_estado && (
                <button onClick={() => avancar(seleccionado.id)} style={{
                  padding: '4px 10px', background: '#0a2342', color: '#fff',
                  border: 'none', borderRadius: 'var(--border-radius-md)',
                  fontSize: 11, cursor: 'pointer', fontFamily: 'inherit',
                }}>
                  Avançar → {seleccionado.proximo_estado}
                </button>
              )}
              <button onClick={() => setSeleccionado(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', fontSize: 16 }}>×</button>
            </div>

            <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>

              {/* Info */}
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{seleccionado.descricao}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                  {seleccionado.tribunal} · {seleccionado.comarca}
                  {seleccionado.valor_causa ? ` · € ${seleccionado.valor_causa.toLocaleString('pt-PT')}` : ''}
                </div>
                <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {seleccionado.partes.map(pt => (
                    <span key={pt.nome} style={{ fontSize: 11, padding: '2px 8px', background: 'var(--color-background-secondary)', borderRadius: 4, color: 'var(--color-text-secondary)' }}>
                      <strong>{pt.papel}:</strong> {pt.nome}
                    </span>
                  ))}
                </div>
              </div>

              {/* Timeline processual */}
              <div>
                <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 10 }}>Fase processual</div>
                <div style={{ display: 'flex', gap: 0 }}>
                  {FASES.slice(0, 7).map((fase, i) => {
                    const idx = seleccionado.estado_index
                    const passado = i < idx
                    const actual = i === idx
                    return (
                      <div key={fase} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                        {i > 0 && (
                          <div style={{ position: 'absolute', left: 0, top: 7, width: '50%', height: 2, background: passado || actual ? '#0a2342' : 'var(--color-border-tertiary)' }} />
                        )}
                        {i < 6 && (
                          <div style={{ position: 'absolute', right: 0, top: 7, width: '50%', height: 2, background: passado ? '#0a2342' : 'var(--color-border-tertiary)' }} />
                        )}
                        <div style={{
                          width: 16, height: 16, borderRadius: '50%', zIndex: 1,
                          background: passado ? '#0a2342' : actual ? '#c4960a' : 'var(--color-background-secondary)',
                          border: `2px solid ${passado ? '#0a2342' : actual ? '#c4960a' : 'var(--color-border-secondary)'}`,
                        }} />
                        <div style={{ fontSize: 9, marginTop: 4, textAlign: 'center', color: actual ? '#0a2342' : passado ? 'var(--color-text-secondary)' : 'var(--color-text-tertiary)', fontWeight: actual ? 600 : 400, lineHeight: 1.2 }}>
                          {fase}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Prazos */}
              {seleccionado.prazos.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 6 }}>Prazos</div>
                  {seleccionado.prazos.map((pr, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '0.5px solid var(--color-border-tertiary)', fontSize: 12 }}>
                      <i className="ti ti-calendar-event" aria-hidden="true" style={{ color: pr.urgente ? 'var(--color-text-danger)' : 'var(--color-text-tertiary)', fontSize: 14 }} />
                      <span style={{ flex: 1 }}>{pr.descricao}</span>
                      <span style={{ fontSize: 11, color: pr.urgente ? 'var(--color-text-danger)' : 'var(--color-text-tertiary)', fontWeight: pr.urgente ? 500 : 400 }}>
                        {new Date(pr.data_limite).toLocaleDateString('pt-PT')}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Histórico de eventos */}
              <div>
                <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 6 }}>Histórico</div>
                <div style={{ maxHeight: 150, overflowY: 'auto' }}>
                  {seleccionado.eventos.map((ev, i) => (
                    <div key={i} style={{ display: 'flex', gap: 8, padding: '4px 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>
                      <span style={{ color: 'var(--color-text-tertiary)', fontSize: 11, flexShrink: 0 }}>
                        {new Date(ev.timestamp).toLocaleDateString('pt-PT')}
                      </span>
                      <span>{ev.descricao}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal novo processo */}
      {mostrarFormNovo && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
          <div style={{ background: 'var(--color-background-primary)', borderRadius: 'var(--border-radius-lg)', width: '100%', maxWidth: 480, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', background: '#0a2342', borderBottom: '2px solid #c4960a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#fff', fontSize: 14, fontWeight: 500 }}>Novo processo jurídico</span>
              <button onClick={() => setMostrarFormNovo(false)} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.6)', cursor: 'pointer', fontSize: 18 }}>×</button>
            </div>
            <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[
                { label: 'Tipo de processo', field: 'tipo', type: 'select', opts: ['laboral','penal','civil','administrativo','familia','dados_pessoais'] },
                { label: 'Descrição', field: 'descricao', type: 'text', ph: 'Breve descrição do caso...' },
                { label: 'Nome do autor', field: 'nome_autor', type: 'text', ph: 'Nome completo ou entidade' },
                { label: 'Nome do réu / arguido', field: 'nome_reu', type: 'text', ph: 'Nome completo ou entidade' },
                { label: 'Comarca', field: 'comarca', type: 'text', ph: 'Lisboa' },
              ].map(f => (
                <div key={f.field}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>
                    {f.label}
                  </label>
                  {f.type === 'select' ? (
                    <select value={(formNovo as any)[f.field]} onChange={e => setFormNovo(prev => ({ ...prev, [f.field]: e.target.value }))} style={{ width: '100%' }}>
                      {f.opts?.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input type="text" value={(formNovo as any)[f.field]} placeholder={f.ph}
                      onChange={e => setFormNovo(prev => ({ ...prev, [f.field]: e.target.value }))}
                      style={{ width: '100%' }} />
                  )}
                </div>
              ))}
              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button onClick={criarProcesso} disabled={criando} style={{
                  flex: 1, padding: '9px', background: '#0a2342', color: '#fff',
                  border: 'none', borderRadius: 'var(--border-radius-md)',
                  fontSize: 13, fontWeight: 500, cursor: criando ? 'not-allowed' : 'pointer',
                  opacity: criando ? 0.7 : 1, fontFamily: 'inherit',
                }}>
                  {criando ? 'A criar...' : 'Criar processo'}
                </button>
                <button onClick={() => setMostrarFormNovo(false)} style={{
                  padding: '9px 16px', background: 'var(--color-background-secondary)',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 'var(--border-radius-md)',
                  fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', color: 'var(--color-text-secondary)',
                }}>
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
