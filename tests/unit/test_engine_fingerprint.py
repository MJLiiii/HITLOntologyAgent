"""Changes to engine resource enforcement must invalidate old check eligibility."""
def test_engine_supervisor_changes_invalidate_configuration(monkeypatch, tmp_path):
    from oe_studio import workflow
    source = tmp_path / 'services/api/src/oe_studio'
    source.mkdir(parents=True)
    supervisor = source / 'engine_process.py'
    supervisor.write_text('resource policy version one')
    monkeypatch.setattr(workflow, '__file__', str(source / 'workflow.py'))
    before = workflow.Studio.engine_configuration(None)
    supervisor.write_text('resource policy version two')
    after = workflow.Studio.engine_configuration(None)
    assert before != after, 'Changing resource enforcement must not reuse previous checked bundles'
