import type { ReactNode } from 'react';
import type { Evidence, Triple } from '../api/generated';
import { Icon, type IconName } from './Icons';
export function Badge({status, children}: {status: string; children?: ReactNode}) {
  const good = ['passed','complete','completed','succeeded','approved','published','resolved'].includes(status);
  const bad = ['failed','error','timeout','rejected','unsupported','stale'].includes(status);
  return <span className={`badge ${good ? 'badge-good' : bad ? 'badge-bad' : 'badge-neutral'}`}><span className="status-dot"/>{children || status.replaceAll('_', ' ')}</span>;
}
export function Empty({icon = 'ontology', title, children}: {icon?: IconName; title: string; children: ReactNode}) {
  return <div className="empty"><div className="empty-icon"><Icon name={icon} size={28}/></div><h3>{title}</h3><p>{children}</p></div>;
}
export function ErrorNotice({message, onDismiss}: {message: string; onDismiss?: () => void}) {
  return <div role="alert" className="notice notice-error"><span>{message}</span>{onDismiss && <button className="icon-button" aria-label="Dismiss error" onClick={onDismiss}><Icon name="close"/></button>}</div>;
}
export function Loading({label = 'Loading workspace…'}: {label?: string}) { return <div role="status" className="loading"><span className="spinner"/>{label}</div>; }
export function short(value: string | null | undefined) { return value ? value.replace(/^sha256:/,'').slice(0, 10) : '—'; }
export function term(value: string) { return value.replace(/^https?:\/\/[^#]*[#/](?=[^/#]+$)/, ''); }
export function date(value?: string | null) { if (!value) return '—'; const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, {month:'short',day:'numeric',year:'numeric'}); }
export function percent(value?: number | null) { return value == null ? '—' : `${Math.round(value * 100)}%`; }
export function TripleTable({triples, variant, compact = false}: {triples: Triple[]; variant?: 'added' | 'deleted'; compact?: boolean}) {
  if (!triples.length) return <p className="muted small">No {variant || ''} triples.</p>;
  return <div className={`table-scroll ${compact ? 'compact-table' : ''}`}><table><thead><tr>{variant && <th className="change-cell" aria-label="Change"/>}<th>Subject</th><th>Relationship</th><th>Object</th></tr></thead><tbody>{triples.map((t,i) => <tr key={`${t.subject}-${t.predicate}-${t.object}-${i}`} className={variant ? `triple-${variant}` : ''}>{variant && <td className="change-cell">{variant === 'added' ? '+' : '−'}</td>}<td><span className="term term-subject" title={t.subject}>{term(t.subject)}</span></td><td><span className="term term-predicate" title={t.predicate}>{term(t.predicate)}</span></td><td><span className="term" title={t.object}>{t.object_type === 'literal' ? `“${t.object}”${t.language ? `@${t.language}` : ''}` : term(t.object)}</span></td></tr>)}</tbody></table></div>;
}
type DisplayEvidence = Pick<Evidence, 'id' | 'title' | 'quote' | 'resolved'> & Partial<Pick<Evidence, 'document_id' | 'locator' | 'content_hash' | 'chunk'>>;
export function EvidenceList({evidence, compact = false}: {evidence: DisplayEvidence[]; compact?: boolean}) {
  return <div className={`evidence-list ${compact ? 'evidence-compact' : ''}`}>{evidence.map((e,i) => <details className="evidence-item" key={e.id} open={!compact}><summary><span className="citation-number">{i+1}</span><span><strong>{e.title}</strong>{e.locator && <span className="muted small">{e.locator}</span>}</span><Badge status={e.resolved ? 'resolved' : 'error'}>{e.resolved ? 'Verified' : 'Unresolved'}</Badge></summary><blockquote>{e.quote}</blockquote><div className="evidence-meta">{e.chunk?.id && <span>Chunk {short(e.chunk.id)}</span>}{e.content_hash && <span title={e.content_hash}>SHA-256 {short(e.content_hash)}</span>}</div></details>)}</div>;
}
export function PanelHeading({title, subtitle, action}: {title: string; subtitle?: string; action?: ReactNode}) { return <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>; }
