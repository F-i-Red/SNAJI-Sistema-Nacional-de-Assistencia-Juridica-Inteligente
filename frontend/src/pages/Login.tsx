import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../auth/session'

const DEMO_CONTAS = [
  { label: 'Cidadão', email: 'cidadao@snaji.gov.pt', password: 'Cidad2024!', cor: '#0a2342' },
  { label: 'Advogado', email: 'advogado@snaji.gov.pt', password: 'Advog2024!', cor: '#185FA5' },
  { label: 'Magistrado', email: 'magistrado@snaji.gov.pt', password: 'Magis2024!', cor: '#0F6E56' },
]

export default function PaginaLogin() {
  const navigate = useNavigate()
  const { login, carregando, erro, limparErro } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await login(email, password)
    if (ok) navigate('/dashboard')
  }

  const loginRapido = async (conta: typeof DEMO_CONTAS[0]) => {
    limparErro()
    setEmail(conta.email)
    setPassword(conta.password)
    const ok = await login(conta.email, conta.password)
    if (ok) navigate('/dashboard')
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--color-background-tertiary)',
      padding: '1.5rem',
    }}>

      {/* Cabeçalho institucional */}
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 36,
          fontWeight: 600,
          color: '#0a2342',
          letterSpacing: '0.04em',
          lineHeight: 1,
        }}>
          SNAJI
        </div>
        <div style={{
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--color-text-tertiary)',
          marginTop: 6,
        }}>
          Sistema Nacional de Assistência Jurídica Inteligente
        </div>
        <div style={{
          fontSize: 11,
          color: 'var(--color-text-tertiary)',
          marginTop: 4,
        }}>
          República Portuguesa
        </div>
      </div>

      {/* Cartão de login */}
      <div style={{
        width: '100%',
        maxWidth: 400,
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        overflow: 'hidden',
      }}>
        <div style={{
          background: '#0a2342',
          borderBottom: '2px solid #c4960a',
          padding: '12px 20px',
        }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: '#fff' }}>
            Autenticação
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>
            Acesso ao sistema jurídico
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.25rem' }}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{
              display: 'block', fontSize: 11, fontWeight: 500,
              textTransform: 'uppercase', letterSpacing: '0.07em',
              color: 'var(--color-text-secondary)', marginBottom: 6,
            }}>
              Endereço electrónico
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="utilizador@snaji.gov.pt"
              required
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{
              display: 'block', fontSize: 11, fontWeight: 500,
              textTransform: 'uppercase', letterSpacing: '0.07em',
              color: 'var(--color-text-secondary)', marginBottom: 6,
            }}>
              Palavra-passe
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{ width: '100%' }}
            />
          </div>

          {erro && (
            <div style={{
              background: 'var(--color-background-danger)',
              border: '0.5px solid var(--color-border-danger)',
              borderRadius: 'var(--border-radius-md)',
              padding: '8px 12px',
              fontSize: 13,
              color: 'var(--color-text-danger)',
              marginBottom: '1rem',
            }}>
              {erro}
            </div>
          )}

          <button
            type="submit"
            disabled={carregando}
            style={{
              width: '100%',
              padding: '10px',
              background: '#0a2342',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--border-radius-md)',
              fontSize: 13,
              fontWeight: 500,
              cursor: carregando ? 'not-allowed' : 'pointer',
              opacity: carregando ? 0.7 : 1,
              fontFamily: 'inherit',
            }}
          >
            {carregando ? 'A autenticar...' : 'Entrar'}
          </button>
        </form>

        {/* Contas demo */}
        <div style={{
          borderTop: '0.5px solid var(--color-border-tertiary)',
          padding: '1rem 1.25rem',
          background: 'var(--color-background-secondary)',
        }}>
          <div style={{
            fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em',
            color: 'var(--color-text-tertiary)', marginBottom: 8, fontWeight: 500,
          }}>
            Contas de demonstração
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {DEMO_CONTAS.map(conta => (
              <button
                key={conta.label}
                onClick={() => loginRapido(conta)}
                disabled={carregando}
                style={{
                  flex: 1, padding: '6px 0',
                  background: 'var(--color-background-primary)',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 'var(--border-radius-md)',
                  fontSize: 11, fontWeight: 500, cursor: 'pointer',
                  color: conta.cor, fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
              >
                {conta.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: '1.5rem', textAlign: 'center' }}>
        Versão 1.0.0 · Fase 1 MVP · Dados de demonstração
      </div>
    </div>
  )
}
