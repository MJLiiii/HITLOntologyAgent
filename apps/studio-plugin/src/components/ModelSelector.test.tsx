import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ModelProfileResponse } from '../api/openapi';
import { ModelSelector, useModelSelection } from './ModelSelector';

const profile = (id:string, overrides:Partial<ModelProfileResponse>={}):ModelProfileResponse => ({id,model:id,provider:'openai',purposes:['chat'],is_default:false,status:'configured_unverified',revision:'revision',max_output_tokens:4096,structured_output:'json_schema',...overrides});
const page=(items:ModelProfileResponse[])=>new Response(JSON.stringify({items,next_cursor:null}));
function Harness({project='p',enabled=true,inherit=false}:{project?:string;enabled?:boolean;inherit?:boolean}) {
  const selection=useModelSelection(project,'chat',{enabled,inherit});
  return <><ModelSelector label="Chat model" selection={selection}/><button disabled={!selection.ready}>Generate</button><output>{selection.profileId||'no override'}</output></>;
}
afterEach(()=>vi.unstubAllGlobals());

describe('server-owned model selection',()=>{
  it('groups authorized GPT and Claude models, selects the default, and leaves missing credentials unavailable',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>page([
      profile('gpt-6.1-terra',{is_default:true}),profile('gpt-4.1'),
      profile('claude-sonnet',{provider:'anthropic'}),profile('claude-opus',{provider:'anthropic',status:'missing_credentials'}),
      profile('extraction-only',{purposes:['extraction']}),
    ])));
    render(<Harness/>);
    expect(screen.getByRole('button',{name:'Generate'})).toBeDisabled();
    await screen.findByRole('group',{name:'OpenAI · GPT'});
    expect(screen.getByRole('group',{name:'Anthropic · Claude'})).toBeInTheDocument();
    expect(screen.getByLabelText('Chat model')).toHaveValue('gpt-6.1-terra');
    expect(screen.getByRole('option',{name:/claude-opus.*API key missing/})).toBeDisabled();
    expect(screen.queryByRole('option',{name:/extraction-only/})).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Chat model'),{target:{value:'claude-sonnet'}});
    expect(screen.getByRole('status')).toHaveTextContent('claude-sonnet');
    expect(screen.getByRole('button',{name:'Generate'})).toBeEnabled();
  });

  it.each([false,true])('requires an explicit choice when the default is absent or unavailable (%s)',async(missingDefault)=>{
    vi.stubGlobal('fetch',vi.fn(async()=>page([profile('available'),...(missingDefault?[profile('unavailable-default',{is_default:true,status:'missing_credentials'})]:[])])));
    render(<Harness/>);
    await screen.findByRole('option',{name:/available · available/});
    expect(screen.getByRole('button',{name:'Generate'})).toBeDisabled();
    expect(screen.getByLabelText('Chat model')).toHaveValue(missingDefault?'unavailable-default':'');
    fireEvent.change(screen.getByLabelText('Chat model'),{target:{value:'available'}});
    expect(screen.getByRole('button',{name:'Generate'})).toBeEnabled();
  });

  it('blocks errors and empty catalogs, and offers a retry without generating a request',async()=>{
    const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({message:'Catalog offline'}),{status:503})).mockResolvedValueOnce(page([]));
    vi.stubGlobal('fetch',fetcher);render(<Harness/>);
    await screen.findByText('Catalog offline');
    expect(screen.getByRole('button',{name:'Generate'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'Retry models'}));
    await screen.findByText('No models are authorized for this action in this project.');
    expect(screen.getByRole('button',{name:'Generate'})).toBeDisabled();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('resets on a project change and ignores a late catalog from the previous project',async()=>{
    let finishFirst!:(response:Response)=>void;
    vi.stubGlobal('fetch',vi.fn((path:string)=>path.includes('/first/')?new Promise<Response>(resolve=>{finishFirst=resolve;}):Promise.resolve(page([profile('second-default',{is_default:true})]))));
    const view=render(<Harness project="first"/>);
    view.rerender(<Harness project="second"/>);
    expect(screen.getByRole('button',{name:'Generate'})).toBeDisabled();
    await screen.findByRole('option',{name:/second-default/});
    finishFirst(page([profile('first-default',{is_default:true})]));
    await waitFor(()=>expect(screen.getByLabelText('Chat model')).toHaveValue('second-default'));
    expect(screen.queryByRole('option',{name:/first-default/})).not.toBeInTheDocument();
  });

  it('keeps deterministic mode explicit and makes no catalog request',()=>{
    const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);render(<Harness enabled={false}/>);
    expect(screen.getByRole('option',{name:'Deterministic demo'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Generate'})).toBeEnabled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('preserves repair inheritance after a successful catalog read without picking a different default',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>page([profile('current-default',{is_default:true})])));
    render(<Harness inherit/>);
    await screen.findByRole('option',{name:/current-default/});
    expect(screen.getByLabelText('Chat model')).toHaveValue('');
    expect(screen.getByRole('option',{name:'Use proposal’s original model'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Generate'})).toBeEnabled();
    expect(screen.getByRole('status')).toHaveTextContent('no override');
  });

  it('still labels repair inheritance when the current session has no configured model',()=>{
    render(<Harness inherit enabled={false}/>);
    expect(screen.getByRole('option',{name:'Use proposal’s original model'})).toBeInTheDocument();
    expect(screen.queryByRole('option',{name:'Deterministic demo'})).not.toBeInTheDocument();
  });
});
