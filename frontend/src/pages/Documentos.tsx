import { useState, useRef } from 'react'
import { api, tratarErroAPI } from '../services/api'

type TipoDoc = 'peticao_inicial' | 'contestacao' | 'recurso' | 'requerimento' | 'queixa_crime'

const TIPOS_DOC: { valor: TipoDoc; label: string; icon: string }[] = [
  { valor: 'peticao_inicial', label: 'Petição inicial', icon: 'ti-file-plus' },
  { valor: 'queixa_crime',   label: 'Queixa-crime',    icon: 'ti-alert-triangle' },
  { valor: 'contestacao',    label: 'Contestação',      icon: 'ti-file-minus' },
  { valor: 'recurso',        label: 'Recurso',          icon: 'ti-arrow-up' },
  { valor: 'requerimento',   label: 'Requerimento',     icon: 'ti-clipboard' },
]

export default function PaginaDocumentos() {
  const [abaSelecionada, setAbaSelecionada] = useState<'gerar' | 'upload'>('gerar')

  // Geração
  const [tipoDoc, setTipoDoc] = useState<TipoDoc>('peticao_inicial')
  const [textoCaso, setTextoCaso] = useState('')
  const [nomeAutor, setNomeAutor] = useState('')
  const [nomeReu, setNomeReu] = useState('')
  const [docGerado, setDocGerado] = useState<{ conteudo: string; titulo: string; advertencia: string } | null>(null)
  const [gerando, setGerando] = useState(false)

  // Upload
  const [ficheiro, setFicheiro] = useState<File | null>(null)
  const [analiseUpload, setAnaliseUpload] = useState<any>(null)
  const [carregandoUpload, setCarregandoUpload] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const [erro, setErro] = useState<string | null>(null)

  const gerarDocumento = async () => {
    if (!textoCaso.trim()) return
    setGerando(true); setErro(null)
    try {
      const r = await api.post('/gerar-documento', {
        tipo: tipoDoc, texto_caso: textoCaso,
        nome_autor: nomeAutor || '[AUTOR]', nome_reu: nomeReu || '[RÉU]',
      })
      setDocGerado(r.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setGerando(false) }
  }

  const uploadFicheiro = async () => {
    if (!ficheiro) return
    setCarregandoUpload(true); setErro(null)
    try {
      const fd = new FormData()
      fd.append('ficheiro', ficheiro)
      fd.append('analisar', 'true')
      const r = await api.post('/documentos/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setAnaliseUpload(r.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregandoUpload(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 900 }}>

      <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
        Documentos jurídicos
      </h1>

      {/* Abas */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
        {[{ id: 'gerar', label: 'Gerar documento', icon: 'ti-file-plus' },
          { id: 'upload', label: 'Analisar documento', icon: 'ti-upload' }].map(aba => (
          <button key={aba.id} onClick={() => setAbaSelecionada(aba.id as any)} style={{
            padding: '8px 16px', background: 'none', fontFamily: 'inherit',
            border: 'none', borderBottom: abaSelecionada === aba.id ? '2px solid #0a2342' : '2px solid transparent',
            fontSize: 13, fontWeight: abaSelecionada === aba.id ? 500 : 400,
            color: abaSelecionada === aba.id ? '#0a2342' : 'var(--color-text-secondary)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            marginBottom: -1,
          }}>
            <i className={`ti ${aba.icon}`} aria-hidden="true" />
            {aba.label}
          </button>
        ))}
      </div>

      {erro && (
        <div style={{ padding: '8px 12px', background: 'var(--color-background-danger)', border: '0.5px solid var(--color-border-danger)', borderRadius: 'var(--border-radius-md)', fontSize: 13, color: 'var(--color-text-danger)' }}>
          {erro}
        </div>
      )}

      {/* Aba: Gerar */}
      {abaSelecionada === 'gerar' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Tipo de documento */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 8 }}>Tipo de documento</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {TIPOS_DOC.map(t => (
                <button key={t.valor} onClick={() => setTipoDoc(t.valor)} style={{
                  padding: '6px 14px', borderRadius: 'var(--border-radius-md)',
                  fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
                  border: '0.5px solid',
                  borderColor: tipoDoc === t.valor ? '#0a2342' : 'var(--color-border-secondary)',
                  background: tipoDoc === t.valor ? '#0a2342' : 'var(--color-background-primary)',
                  color: tipoDoc === t.valor ? '#fff' : 'var(--color-text-secondary)',
                  display: 'flex', alignItems: 'center', gap: 5,
                }}>
                  <i className={`ti ${t.icon}`} aria-hidden="true" style={{ fontSize: 13 }} />
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Campos */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>Nome do autor / queixoso</label>
              <input type="text" value={nomeAutor} onChange={e => setNomeAutor(e.target.value)} placeholder="Nome completo ou entidade" style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>Nome do réu / arguido</label>
              <input type="text" value={nomeReu} onChange={e => setNomeReu(e.target.value)} placeholder="Nome completo ou entidade" style={{ width: '100%' }} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>Descrição do caso</label>
            <textarea value={textoCaso} onChange={e => setTextoCaso(e.target.value)}
              placeholder="Descreva os factos relevantes do caso. Quanto mais detalhe, melhor o documento gerado..."
              rows={5} style={{ width: '100%' }} />
          </div>

          <button onClick={gerarDocumento} disabled={gerando || !textoCaso.trim()} style={{
            alignSelf: 'flex-start', padding: '8px 20px', background: '#0a2342', color: '#fff',
            border: 'none', borderRadius: 'var(--border-radius-md)',
            fontSize: 13, fontWeight: 500,
            cursor: gerando || !textoCaso.trim() ? 'not-allowed' : 'pointer',
            opacity: gerando || !textoCaso.trim() ? 0.6 : 1, fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <i className="ti ti-file-plus" aria-hidden="true" />
            {gerando ? 'A gerar...' : 'Gerar documento ↗'}
          </button>

          {/* Resultado */}
          {docGerado && (
            <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', flex: 1 }}>
                  {docGerado.titulo}
                </span>
                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 20, background: 'var(--color-background-warning)', color: 'var(--color-text-warning)', fontWeight: 500 }}>
                  Rever com advogado
                </span>
                <button onClick={() => navigator.clipboard?.writeText(docGerado.conteudo)} style={{
                  padding: '4px 10px', background: 'var(--color-background-secondary)',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 'var(--border-radius-md)', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit',
                  color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: 4,
                }}>
                  <i className="ti ti-copy" aria-hidden="true" /> Copiar
                </button>
              </div>
              <div style={{ padding: 14 }}>
                <div style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--color-background-warning)', borderRadius: 'var(--border-radius-md)', fontSize: 11, color: 'var(--color-text-warning)', lineHeight: 1.5 }}>
                  <i className="ti ti-alert-triangle" aria-hidden="true" /> {docGerado.advertencia}
                </div>
                <pre style={{
                  fontFamily: "'Cormorant Garamond', serif", fontSize: 13,
                  lineHeight: 1.9, color: 'var(--color-text-primary)',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  background: 'var(--color-background-secondary)',
                  borderRadius: 'var(--border-radius-md)', padding: '1rem',
                  maxHeight: 400, overflowY: 'auto',
                }}>
                  {docGerado.conteudo}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Aba: Upload */}
      {abaSelecionada === 'upload' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Zona de drop */}
          <div
            onClick={() => inputRef.current?.click()}
            style={{
              border: '2px dashed var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-lg)',
              padding: '2rem', textAlign: 'center', cursor: 'pointer',
              background: ficheiro ? 'var(--color-background-success)' : 'var(--color-background-secondary)',
              transition: 'all 0.15s',
            }}
          >
            <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }}
              onChange={e => { if (e.target.files?.[0]) setFicheiro(e.target.files[0]) }} />
            <i className="ti ti-upload" aria-hidden="true" style={{ fontSize: 28, color: 'var(--color-text-tertiary)', display: 'block', marginBottom: 8 }} />
            {ficheiro ? (
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-primary)' }}>{ficheiro.name}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 2 }}>
                  {(ficheiro.size / 1024).toFixed(0)} KB · Clique para mudar
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>Clique para seleccionar ficheiro</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 4 }}>PDF, DOCX ou TXT · Máximo 10MB</div>
              </div>
            )}
          </div>

          {ficheiro && (
            <button onClick={uploadFicheiro} disabled={carregandoUpload} style={{
              alignSelf: 'flex-start', padding: '8px 20px', background: '#0a2342', color: '#fff',
              border: 'none', borderRadius: 'var(--border-radius-md)',
              fontSize: 13, fontWeight: 500,
              cursor: carregandoUpload ? 'not-allowed' : 'pointer',
              opacity: carregandoUpload ? 0.6 : 1, fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <i className="ti ti-search" aria-hidden="true" />
              {carregandoUpload ? 'A analisar...' : 'Analisar documento ↗'}
            </button>
          )}

          {/* Resultado upload */}
          {analiseUpload && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>{analiseUpload.nome}</div>
                <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 12 }}>
                  <span><strong>Tipo:</strong> {analiseUpload.tipo}</span>
                  <span><strong>Páginas:</strong> {analiseUpload.num_paginas}</span>
                  <span><strong>Caracteres:</strong> {analiseUpload.num_caracteres.toLocaleString('pt-PT')}</span>
                </div>
                {analiseUpload.avisos?.length > 0 && (
                  <div style={{ padding: '6px 10px', background: 'var(--color-background-warning)', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: 'var(--color-text-warning)', marginBottom: 10 }}>
                    {analiseUpload.avisos.join(' · ')}
                  </div>
                )}
                {analiseUpload.analise && (
                  <div>
                    <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 6 }}>Análise automática</div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
                      Tipo identificado: <strong>{analiseUpload.analise.tipo_processo}</strong>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
                      {analiseUpload.analise.qualificacao}
                    </div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {analiseUpload.analise.normas?.map((n: any) => (
                        <span key={`${n.diploma}-${n.artigo}`} style={{ fontSize: 11, padding: '2px 8px', background: 'var(--color-background-secondary)', borderRadius: 4, color: 'var(--color-text-secondary)' }}>
                          {n.diploma} Art. {n.artigo}.º
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
