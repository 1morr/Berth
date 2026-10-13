const fs=require('fs'),path=require('path')
const web=process.argv[2]
const ts=require(path.join(web,'node_modules/typescript'))
const src=fs.readFileSync(path.join(web,'src/i18n/resources.ts'),'utf8')
const js=ts.transpileModule(src,{compilerOptions:{module:'commonjs',target:'es2020'}}).outputText
const m={exports:{}};new Function('module','exports',js)(m,m.exports)
const flat=(o,p='')=>Object.entries(o).flatMap(([k,v])=>typeof v==='string'?[p?p+'.'+k:k]:flat(v,p?p+'.'+k:k))
const zh=flat(m.exports.resources['zh-Hant'].translation)
const files=[];(function w(d){for(const f of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,f.name);if(f.isDirectory())w(p);else if(/\.(ts|tsx)$/.test(f.name)&&!/schema\.d\.ts$|i18n[\/]resources\.ts$/.test(p))files.push(p)}})(path.join(web,'src'))
const isTest=f=>/\.test\.|[\/]test[\/]|setupTests/.test(f)
const lit={prod:new Set(),test:new Set()}, heads={prod:new Set(),test:new Set()}
const strsOf={}
for(const f of files){
  const sf=ts.createSourceFile(f,fs.readFileSync(f,'utf8'),ts.ScriptTarget.Latest,true,f.endsWith('x')?ts.ScriptKind.TSX:ts.ScriptKind.TS)
  const k=isTest(f)?'test':'prod'
  ;(function v(n){
    if(ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n)){lit[k].add(n.text)}
    else if(ts.isTemplateHead(n)){heads[k].add(n.text)}
    else if(ts.isTemplateMiddle(n)){}
    ts.forEachChild(n,v)
  })(sf)
}
const base=k=>k.replace(/_(one|other|zero|few|many|two)$/,'')
const keys=[...new Set(zh.map(base))]
const hp=[...heads.prod].filter(h=>h.includes('.')||h.length>2)
const ht=[...heads.test].filter(h=>h.includes('.'))
const res={used:0,dyn:[],testOnly:[],unused:[]}
for(const k of keys){
  if(lit.prod.has(k)){res.used++;continue}
  const p=hp.find(h=>k.startsWith(h))
  if(p){res.dyn.push([k,p]);continue}
  // a literal that is a prefix of key (e.g. 'a.b.' + x or keyPrefix)
  const pl=[...lit.prod].find(s=>s.endsWith('.')&&k.startsWith(s))
  if(pl){res.dyn.push([k,pl]);continue}
  if(lit.test.has(k)||ht.find(h=>k.startsWith(h))){res.testOnly.push(k);continue}
  res.unused.push(k)
}
console.log('keys',keys.length,'used',res.used,'dyn',res.dyn.length,'testOnly',res.testOnly.length,'unused',res.unused.length)
fs.writeFileSync(path.join(process.cwd(),'i18n_out2.json'),JSON.stringify(res,null,1))
console.log([...heads.prod].sort().join('\n'))
