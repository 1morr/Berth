const fs=require('fs'),path=require('path')
const web=process.argv[2]
const ts=require(path.join(web,'node_modules/typescript'))
const src=fs.readFileSync(path.join(web,'src/i18n/resources.ts'),'utf8')
const js=ts.transpileModule(src,{compilerOptions:{module:'commonjs',target:'es2020'}}).outputText
const m={exports:{}};new Function('module','exports',js)(m,m.exports)
const flat=(o,p='')=>Object.entries(o).flatMap(([k,v])=>typeof v==='string'?[[p?p+'.'+k:k,v]]:flat(v,p?p+'.'+k:k))
const en=flat(m.exports.resources.en.translation)
const g={};for(const [k,v] of en){if(v.length<14||/^\{\{/.test(v))continue;(g[v]=g[v]||[]).push(k)}
for(const [v,ks] of Object.entries(g)){const base=[...new Set(ks.map(k=>k.replace(/_(one|other)$/,'')))];if(base.length>1)console.log(JSON.stringify(v.slice(0,70)),base.join(' | '))}
