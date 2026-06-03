import { useState, useRef } from 'react'
import type { AnalysisResponse, TipoProcesso } from '../types'
import { juridicalService, tratarErroAPI } from '../services/api'
import { useAuthStore } from '../auth/session'

const EXEMPLOS = {
  laboral: 'Fui despedido sem justa causa após 8 anos de serviço ininterrupto. O meu empregador alega baixo rendimento mas nunca me deu nenhum aviso ou processo disciplinar. Recusa-se a pagar qualquer indemnização.',
  penal: 'Fui vítima de ameaças de morte repetidas por parte do meu ex-cônjuge. Tenho mensagens escritas como prova. Quero saber como apresentar queixa-crime e que medidas de coacção posso pedir.',
  rgpd: 'Uma empresa de telecomunicações partilhou os meus dados pessoais com parceiros comerciais sem o meu consentimento e recusou o pedido de apagamento. Quais os meus direitos ao abrigo do RGPD?',
}

const CORES_TIPO: Record<string, string> = {
  laboral: 'var(--color-text-info)',
  penal: 'var(--color-text-danger)',
  civil: 'var(--color-text-warning)',
  dados_pessoais: 'var(--color-text-success)',
  familia: 'var(--color-text-info)',
  outro: 'var(--color-text-secondary)',
}

const PASSOS_PIPELINE = ['Recepção', 'RAG', 'Classificação', 'Análise', 'Contraditório', 'Auditoria']

export default function PaginaConsulta() {
  const { utilizador } = useAuthStore()
  const [texto, setTexto] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [passoActual, setPassoActual] = useState(-1)
  const [resultado, setResultado] = useState<AnalysisResponse | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const resultadoRef = useRef<HTMLDivElement>(null)

  const avancarPasso = (p: number) => setPassoActual(p)

  const analisar = async () => {
    if (!texto.trim() || carregando) return
    setCarregando(true)
    setErro(null)
    setResultado(null)
    setPassoActual(0)

    try {
      const delay = (ms: number) => new Promise(r => setTimeout(r, ms))
      await delay(300); avancarPasso(1)
      await delay(400); avancarPasso(2)
      await delay(300); avancarPasso(3)

      const res = await juridicalService.analisar({ texto, fontes: ['CRP', 'CT', 'CC', 'RGPD', 'CP', 'CPC'] })

      avancarPasso(4)
      await delay(300)
      avancarPasso(5)
      await delay(200)

      setResultado(res)
      setTimeout(() => resultadoRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (e) {
      setErro(tratarErroAPI(e))
    } finally {
      setCarregando(false)
      setPassoActual(-1)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 900 }}>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 22, fontWeight: 500,
          color: 'var(--color-text-primary)',
        }}>
          {utilizador?.role === 'magistrado' ? 'Pesquisa jurídica' : 'Consulta jurídica'}
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Motor RAG · 246 artigos reais · 6 diplomas
        </small>
      </div>

      {/* Área de input */}
      <div style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        overflow: 'hidden',
      }}>
        <div style={{
          fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
          letterSpacing: '0.07em', color: 'var(--color-text-tertiary)',
          padding: '10px 14px 6px',
        }}>
          Descrição do caso
        </div>
        <textarea
          value={texto}
          onChange={e => setTexto(e.target.value)}
          placeholder="Descreva o caso em linguagem natural. Quanto mais detalhe, mais precisa será a análise..."
          rows={4}
          style={{
            width: '100%', padding: '0 14px 10px',
            fontFamily: 'inherit', fontSize: 14,
            background: 'transparent', border: 'none',
            resize: 'vertical', color: 'var(--color-text-primary)',
            lineHeight: 1.6, outline: 'none',
          }}
        />
        <div style={{
          borderTop: '0.5px solid var(--color-border-tertiary)',
          padding: '8px 14px',
          display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        }}>
          <button
            onClick={analisar}
            disabled={carregando || !texto.trim()}
            style={{
              padding: '7px 18px',
              background: '#0a2342', color: '#fff',
              border: 'none', borderRadius: 'var(--border-radius-md)',
              fontSize: 13, fontWeight: 500,
              cursor: carregando || !texto.trim() ? 'not-allowed' : 'pointer',
              opacity: carregando || !texto.trim() ? 0.6 : 1,
              fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <i className="ti ti-scale" aria-hidden="true" />
            {carregando ? 'A analisar...' : 'Analisar caso ↗'}
          </button>
          {Object.entries(EXEMPLOS).map(([chave, val]) => (
            <button
              key={chave}
              onClick={() => setTexto(val)}
              style={{
                background: 'none', border: 'none',
                fontSize: 12, color: 'var(--color-text-secondary)',
                cursor: 'pointer', textDecoration: 'underline',
                textUnderlineOffset: 3, fontFamily: 'inherit',
              }}
            >
              Exemplo {chave}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline de progresso */}
      {carregando && (
        <div style={{
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-lg)',
          padding: '12px 14px',
          display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', fontWeight: 500, marginRight: 4 }}>Pipeline:</span>
          {PASSOS_PIPELINE.map((passo, i) => (
            <span key={passo} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                fontSize: 11, padding: '3px 10px', borderRadius: 20,
                border: '0.5px solid var(--color-border-tertiary)',
                background: i < passoActual ? 'var(--color-background-success)' : i === passoActual ? 'var(--color-background-info)' : 'transparent',
                color: i < passoActual ? 'var(--color-text-success)' : i === passoActual ? 'var(--color-text-info)' : 'var(--color-text-tertiary)',
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                {passo}
              </span>
              {i < PASSOS_PIPELINE.length - 1 && <span style={{ color: 'var(--color-text-tertiary)', fontSize: 10 }}>›</span>}
            </span>
          ))}
        </div>
      )}

      {/* Erro */}
      {erro && (
        <div style={{
          background: 'var(--color-background-danger)',
          border: '0.5px solid var(--color-border-danger)',
          borderRadius: 'var(--border-radius-md)',
          padding: '12px 14px', fontSize: 13,
          color: 'var(--color-text-danger)',
        }}>
          <strong>Erro:</strong> {erro}
        </div>
      )}

      {/* Resultado */}
      {resultado && (
        <div ref={resultadoRef} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Normas identificadas */}
          <div style={{
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-lg)',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '10px 14px',
              borderBottom: '0.5px solid var(--color-border-tertiary)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <i className="ti ti-book-2" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-secondary)' }} />
              <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', flex: 1 }}>
                Normas identificadas pelo motor RAG
              </span>
              {resultado.audit.grounded
                ? <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--color-background-success)', color: 'var(--color-text-success)', fontWeight: 500 }}>
                    <i className="ti ti-shield-check" aria-hidden="true" style={{ fontSize: 10 }} /> grounded
                  </span>
                : <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--color-background-warning)', color: 'var(--color-text-warning)', fontWeight: 500 }}>
                    verificar citações
                  </span>
              }
            </div>
            <div style={{ padding: 14 }}>
              {resultado.normas.map(n => (
                <span key={`${n.diploma}-${n.artigo}`} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: 11, padding: '4px 10px', borderRadius: 6,
                  background: 'var(--color-background-secondary)',
                  border: '0.5px solid var(--color-border-tertiary)',
                  margin: 2,
                }}>
                  <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{n.diploma}</span>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Art. {n.artigo}.º</span>
                  {n.epigrase && <span style={{ color: 'var(--color-text-tertiary)' }}>{n.epigrase}</span>}
                </span>
              ))}
            </div>
          </div>

          {/* Análise + Vias */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>

            <div style={{
              background: 'var(--color-background-primary)',
              border: '0.5px solid var(--color-border-tertiary)',
              borderRadius: 'var(--border-radius-lg)',
              overflow: 'hidden',
            }}>
              <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <i className="ti ti-file-description" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-secondary)' }} />
                <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>Análise jurídica</span>
              </div>
              <div style={{ padding: 14, fontSize: 13, lineHeight: 1.8, color: 'var(--color-text-primary)' }}>
                <div style={{ marginBottom: 8, padding: '6px 10px', background: 'var(--color-background-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12 }}>
                  <strong>Qualificação:</strong> {resultado.qualificacao_juridica}
                </div>
                {resultado.analise}
              </div>
            </div>

            <div style={{
              background: 'var(--color-background-primary)',
              border: '0.5px solid var(--color-border-tertiary)',
              borderRadius: 'var(--border-radius-lg)',
              overflow: 'hidden',
            }}>
              <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <i className="ti ti-route" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-secondary)' }} />
                <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>Vias processuais</span>
              </div>
              <div style={{ padding: 14 }}>
                {resultado.vias_processuais.map((v, i) => (
                  <div key={i} style={{
                    display: 'flex', gap: 8, padding: '6px 0',
                    borderBottom: '0.5px solid var(--color-border-tertiary)',
                    fontSize: 13,
                  }}>
                    <span style={{ color: 'var(--color-text-tertiary)', fontSize: 11, marginTop: 2 }}>{i + 1}</span>
                    {v}
                  </div>
                ))}
                <div style={{
                  marginTop: 10, padding: '8px 10px',
                  background: 'var(--color-background-info)',
                  borderRadius: 'var(--border-radius-md)',
                  fontSize: 12, color: 'var(--color-text-info)',
                }}>
                  <i className="ti ti-info-circle" aria-hidden="true" /> {resultado.conclusao}
                </div>
              </div>
            </div>
          </div>

          {/* Contraditório */}
          {resultado.contraditorio && (
            <div style={{
              background: 'var(--color-background-primary)',
              border: '0.5px solid var(--color-border-tertiary)',
              borderRadius: 'var(--border-radius-lg)',
              overflow: 'hidden',
            }}>
              <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <i className="ti ti-scales" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-secondary)' }} />
                <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>Análise contraditória</span>
              </div>
              <div style={{ padding: 14, fontSize: 13, lineHeight: 1.8, color: 'var(--color-text-secondary)' }}>
                {resultado.contraditorio}
              </div>
            </div>
          )}

          {/* Auditoria */}
          <div style={{
            background: 'var(--color-background-secondary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-md)',
            padding: '10px 14px',
            display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
            fontSize: 11, color: 'var(--color-text-tertiary)',
          }}>
            <i className="ti ti-shield-check" aria-hidden="true" style={{ fontSize: 14 }} />
            <span>Caso: <code style={{ fontFamily: 'monospace' }}>{resultado.caso_id.slice(0, 8)}</code></span>
            <span>Normas citadas: {resultado.audit.normas_citadas}</span>
            <span>Fontes: {resultado.audit.fontes_utilizadas.join(', ')}</span>
            <span>Motor: {resultado.audit.modelo}</span>
            <span style={{ marginLeft: 'auto', color: resultado.audit.grounded ? 'var(--color-text-success)' : 'var(--color-text-warning)' }}>
              {resultado.audit.grounded ? '✓ Grounded' : '⚠ Verificar'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
