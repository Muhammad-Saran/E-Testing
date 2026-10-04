import { createContext, useCallback, useContext, useState } from 'react'
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'

const ToastContext = createContext(null)
const ICONS = { ok: CheckCircle2, err: XCircle, info: Info }

// Small transient messages in the corner: toast.ok('Saved'), toast.err('Failed').
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])
  const push = useCallback((type, title, text) => {
    const id = Date.now() + Math.random()
    setToasts((list) => [...list.slice(-3), { id, type, title, text }])
    setTimeout(() => dismiss(id), type === 'err' ? 6000 : 3800)
  }, [dismiss])

  const api = {
    ok: (title, text) => push('ok', title, text),
    err: (title, text) => push('err', title, text),
    info: (title, text) => push('info', title, text),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.type]
          return (
            <div key={t.id} className={`toast ${t.type}`}>
              <Icon size={19} className="toast-icon" />
              <div><strong>{t.title}</strong>{t.text && <span className="muted">{t.text}</span>}</div>
              <button onClick={() => dismiss(t.id)} aria-label="Dismiss"><X size={16} /></button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
