import { GraduationCap, ShieldCheck, Sparkles, Timer, TrendingUp } from 'lucide-react'

const FEATURES = [
  { icon: Sparkles, title: 'AI question generation', text: 'A T5 Transformer turns lecture notes into reviewed questions.' },
  { icon: Timer, title: 'Secure timed exams', text: 'Server-enforced timers, question pools and live proctoring signals.' },
  { icon: ShieldCheck, title: 'Instant, fair grading', text: 'Semantic short-answer grading with instructor review.' },
  { icon: TrendingUp, title: 'Actionable analytics', text: 'Item analysis, trends and at-risk students at a glance.' },
]

// Split-screen frame for the sign-in / registration pages.
export default function AuthLayout({ children, wide }) {
  return (
    <div className="auth-screen">
      <aside className="auth-brand">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark" style={{ background: 'rgba(255,255,255,0.18)' }}><GraduationCap size={21} /></div>
          <div>
            <div className="brand-name">e-Testing Service</div>
            <div className="brand-sub" style={{ color: 'rgba(255,255,255,0.75)' }}>COMSATS University Islamabad, Abbottabad</div>
          </div>
        </div>
        <div>
          <h2>Assessment, reimagined for the modern classroom.</h2>
          <p>Create, deliver and grade examinations in one secure platform — with AI doing the heavy lifting.</p>
          <div className="auth-features">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="auth-feature">
                <div className="fi"><Icon size={19} /></div>
                <div><strong>{title}</strong><span>{text}</span></div>
              </div>
            ))}
          </div>
        </div>
        <p style={{ fontSize: '0.8rem', opacity: 0.7 }}>Final Year Project · BS Computer Science 2022–2026</p>
      </aside>
      <main className="auth-panel">
        <div className={`auth-card ${wide ? 'wide' : ''}`}>{children}</div>
      </main>
    </div>
  )
}

export function AuthBrand() {
  return (
    <div className="brand-lg">
      <div className="brand-mark" style={{ width: 34, height: 34 }}><GraduationCap size={18} /></div>
      e-Testing
    </div>
  )
}
