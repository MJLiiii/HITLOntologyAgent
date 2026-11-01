import { useEffect, useState } from 'react';
import type { Experiment, Project, Proposal, ReviewDecision, Revision, Session } from '../../api/generated';
import type { ExperimentReviewLink } from '../../api/openapi';
import { errorMessage, list, post, request } from '../../api/client';
import { Badge, ErrorNotice, Loading } from '../../components/ui';
import { Icon } from '../../components/Icons';

export function ExperimentReview({run, project, proposals, session, onRefresh, onOpenProposal, onLinked}: {
  run: Experiment; project: Project; proposals: Proposal[]; session: Session;
  onRefresh: () => Promise<void>; onOpenProposal: (id: string) => void; onLinked: (run: Experiment) => void;
}) {
  const [staged, setStaged] = useState<Revision|null>(null);
  const [reviews, setReviews] = useState<ReviewDecision[]>([]);
  const [reviewId, setReviewId] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const candidate = proposals.find(proposal => proposal.experiment_run_id === run.id) || staged;
  const review = reviews.find(item => item.id === reviewId);
  const base = `/projects/${encodeURIComponent(project.id)}`;
  const isHuman = session.actor.kind === 'human' && session.actor.roles.includes('approver');

  useEffect(() => {
    if (!candidate?.revision_id) return;
    let active = true;
    setLoading(true); setError(''); setReviews([]); setReviewId('');
    void list<ReviewDecision>(`${base}/reviews?revision_id=${encodeURIComponent(candidate.revision_id)}`)
      .then(items => { if (active) setReviews(items.filter(item => item.actor.kind === 'human')); })
      .catch(err => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, candidate?.revision_id, candidate?.status]);

  async function stageCandidate() {
    setBusy(true); setError(''); setNotice('');
    try {
      const revision = await request<Revision>(`${base}/experiments/${encodeURIComponent(run.id)}/proposal`, {method:'POST'});
      setStaged(revision);
      await onRefresh();
      setNotice(`Candidate revision ${revision.revision} staged. Run its checks and record any human decision in Proposals. No approval was created.`);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function linkReview() {
    if (!review || !isHuman) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await post<Experiment>(`${base}/experiments/${encodeURIComponent(run.id)}/review-results`, {review_id:review.id} satisfies ExperimentReviewLink);
      await onRefresh();
      onLinked(result);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }

  return <section className="experiment-review">
    <div className="section-heading"><h3>Bring condition D into human review</h3><Icon name="shield" size={20}/></div>
    <p className="muted small">Stage the frozen output as an unapproved candidate, complete its checks and review in Proposals, then link that persisted decision. The pre-review record stays unchanged.</p>
    {error && <ErrorNotice message={error}/>}
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    <div className="experiment-review-actions">{candidate ? <button className="button button-secondary" disabled={busy} onClick={() => onOpenProposal(candidate.id)}>Open candidate revision {candidate.revision}<Icon name="chevron" size={14}/></button> : <button className="button button-primary" disabled={busy || !!project.pending_publication_id} onClick={() => void stageCandidate()}>{busy?'Staging…':'Stage condition D candidate'}</button>}</div>
    {candidate && <>
      <p className="muted small">Use the explicit review timer in Proposals if you want active correction time recorded. An absent or incomplete timer stays unavailable.</p>
      {loading ? <Loading label="Loading recorded human decisions…"/> : reviews.length ? <>
        <label>Recorded human decision<select value={reviewId} onChange={event => setReviewId(event.target.value)} disabled={busy}><option value="">Select a persisted review</option>{reviews.map(item => <option value={item.id} key={item.id}>{item.actor.subject} · {item.decision.replaceAll('_',' ')} · {item.id}</option>)}</select></label>
        {review && <article className="experiment-review-record"><div className="section-heading"><strong>{review.actor.subject}</strong><Badge status={review.decision}>{review.decision.replaceAll('_',' ')}</Badge></div><p>{review.rationale}</p><p className="small muted">Exact bundle <code>{review.bundle_digest}</code></p><a href={`/api/v1${base}/reviews/${encodeURIComponent(review.id)}`} target="_blank" rel="noreferrer">Inspect persisted review<Icon name="external" size={12}/></a></article>}
        <button className="button button-primary" disabled={busy || !review || !isHuman} onClick={() => void linkReview()}>{busy?'Linking…':'Link review as new post-review record'}</button>
        {!isHuman && <p className="action-reason">An authorized human approver session is required to link a review.</p>}
      </> : <p className="action-reason">No human decision is recorded for this candidate revision. Complete its review in Proposals, then refresh the workspace.</p>}
    </>}
  </section>;
}
