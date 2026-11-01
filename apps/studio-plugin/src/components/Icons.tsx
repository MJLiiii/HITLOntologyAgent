export type IconName = 'chat' | 'ontology' | 'sources' | 'proposals' | 'validation' | 'experiments' | 'arrow' | 'plus' | 'chevron' | 'search' | 'check' | 'close' | 'external' | 'refresh' | 'download' | 'file' | 'clock' | 'shield' | 'spark' | 'menu' | 'branch';
const paths: Record<IconName, string> = {
  chat: 'M21 11.5a8.3 8.3 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.3 8.3 0 0 1-3.8-.9L3 21l1.9-5.7a8.3 8.3 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.3 8.3 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z',
  ontology: 'M12 3v5M5 16v-4h14v4M12 12v4M9 3h6v5H9zM2 16h6v5H2zM9 16h6v5H9zM16 16h6v5h-6z',
  sources: 'M20 21H4V3h11l5 5v13ZM14 3v6h6M8 13h8M8 17h5',
  proposals: 'M8 3v12a4 4 0 0 0 4 4h4M8 7h8M16 3v8M4 3h8M13 16l3 3-3 3',
  validation: 'M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4ZM8 12l3 3 5-6',
  experiments: 'M4 20h16M7 16v-5M12 16V4M17 16V8',
  arrow: 'M12 19V5M5 12l7-7 7 7',
  plus: 'M12 5v14M5 12h14', chevron: 'm9 5 7 7-7 7', search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  check: 'm5 12 4 4L19 6', close: 'm6 6 12 12M6 18 18 6', external: 'M15 3h6v6M10 14 21 3M21 14v7H3V3h7',
  refresh: 'M21 7v5h-5M3 17v-5h5M5 7a8 8 0 0 1 13-2l3 7M3 12l3 7a8 8 0 0 0 13-2',
  download: 'M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5', file: 'M14 2H4v20h16V8l-6-6ZM14 2v6h6M8 13h8M8 17h6',
  clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0ZM12 6v6l4 2',
  shield: 'M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4ZM8 12l3 3 5-6',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z', menu: 'M4 6h16M4 12h16M4 18h16',
  branch: 'M6 3v12a4 4 0 1 0 4 4M6 7h8a4 4 0 0 0 4-4M3 3h6M15 3h6M10 19h4',
};
export function Icon({name, size = 18, className = ''}: {name: IconName; size?: number; className?: string}) {
  return <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]}/></svg>;
}
