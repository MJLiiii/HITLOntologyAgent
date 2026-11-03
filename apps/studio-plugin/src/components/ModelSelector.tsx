import { useEffect, useState } from 'react';
import type { ModelProfileResponse } from '../api/openapi';
import { errorMessage, list } from '../api/client';
import { ErrorNotice } from './ui';

type Purpose = 'chat'|'proposal'|'repair'|'experiment'|'extraction'|'test_generation';
type Catalog = {scope:string;profiles:ModelProfileResponse[];selected:string;loading:boolean;error:string};

export function useModelSelection(projectId:string, purpose:Purpose, {enabled=true,inherit=false}:{enabled?:boolean;inherit?:boolean}={}) {
  const scope=JSON.stringify([projectId,purpose,enabled,inherit]);
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [reload,setReload]=useState(0);
  useEffect(()=>{
    if(!enabled){setCatalog(null);return;}
    let active=true;
    setCatalog({scope,profiles:[],selected:'',loading:true,error:''});
    list('GET /api/v1/projects/{p}/model-profiles',{path:{p:projectId}}).then(items=>{
      if(!active)return;
      const profiles=items.filter(item=>item.purposes.includes(purpose));
      setCatalog({scope,profiles,selected:inherit?'':profiles.find(item=>item.is_default)?.id||'',loading:false,error:''});
    }).catch(error=>{if(active)setCatalog({scope,profiles:[],selected:'',loading:false,error:errorMessage(error)});});
    return()=>{active=false;};
  },[projectId,purpose,enabled,inherit,scope,reload]);
  const current=catalog?.scope===scope?catalog:null;
  const profiles=enabled?current?.profiles||[]:[];
  const selected=enabled?current?.selected||'':'';
  const loading=enabled&&(!current||current.loading);
  const error=enabled?current?.error||'':'';
  const ready=!enabled||(!loading&&!error&&((inherit&&!selected)||profiles.some(item=>item.id===selected&&item.status==='configured_unverified')));
  return {
    profiles,selected,loading,error,enabled,inherit,ready,profileId:enabled&&ready&&selected?selected:undefined,
    select(id:string) {
      if(loading||error||(id&&!profiles.some(item=>item.id===id&&item.status==='configured_unverified')))return false;
      setCatalog(value=>value?.scope===scope?{...value,selected:id}:value);return true;
    },
    retry() {setCatalog(null);setReload(value=>value+1);},
  };
}

export function ModelSelector({label,selection,disabled=false,onChange}:{label:string;selection:ReturnType<typeof useModelSelection>;disabled?:boolean;onChange?:()=>void}) {
  const {profiles,selected,enabled,inherit,loading,error}=selection;
  return <div className="model-selector">
    <label>{label}<select value={selected} disabled={disabled||loading||!enabled} onChange={event=>{if(selection.select(event.target.value))onChange?.();}}>
      <option value="">{loading?'Loading models…':inherit?'Use proposal’s original model':!enabled?'Deterministic demo':'Select a model'}</option>
      {(['openai','anthropic'] as const).map(provider=>{
        const choices=profiles.filter(item=>item.provider===provider);
        return !!choices.length&&<optgroup key={provider} label={provider==='openai'?'OpenAI · GPT':'Anthropic · Claude'}>{choices.map(item=><option key={item.id} value={item.id} disabled={item.status!=='configured_unverified'}>{item.model} · {item.id}{item.is_default?' · default':''}{item.status==='missing_credentials'?' · API key missing':item.status!=='configured_unverified'?' · unavailable':''}</option>)}</optgroup>;
      })}
    </select></label>
    {error&&<><ErrorNotice message={error}/><button className="text-button small" type="button" onClick={selection.retry} disabled={disabled}>Retry models</button></>}
    {enabled&&!loading&&!error&&!profiles.length&&!inherit&&<p className="action-reason">No models are authorized for this action in this project.</p>}
    {profiles.some(item=>item.status==='missing_credentials')&&<p className="field-help">Unavailable models need their provider API key configured on the server.</p>}
  </div>;
}
