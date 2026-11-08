const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('ui.js','utf8').replace("import {DiscordSDK} from '@discord/embedded-app-sdk';",'');
async function scenario(mode){
 const elements=new Map(),calls=[];
 function element(id){if(!elements.has(id))elements.set(id,{textContent:'',value:'1000',hidden:false,clientWidth:600,clientHeight:300,width:0,height:0,style:{},classList:{toggle(){},add(){},remove(){}},replaceChildren(){},append(){},getContext(){return new Proxy({createLinearGradient(){return {addColorStop(){}}}}, {get(t,k){return k in t?t[k]:()=>{}}})}});return elements.get(id)}
 const state={is_admin:false,balance:0,name:'Test',roles:[],history:[],prizes:[],crash:null};
 class SDK{constructor(){this.guildId='123';this.commands={authorize:async()=>({code:'test-code'}),authenticate:async()=>({})}}ready(){return mode==='timeout'?new Promise(()=>{}):Promise.resolve()}}
 const context={DiscordSDK:SDK,document:{hidden:false,getElementById:element,querySelectorAll:()=>[],createElement:()=>({append(){}})},window:{addEventListener(){}},location:{protocol:'https:',search:mode==='outside'?'':'?frame_id=test'},URLSearchParams,performance,matchMedia:()=>({matches:false}),devicePixelRatio:1,requestAnimationFrame:()=>1,setInterval:()=>1,AbortController,crypto:require('node:crypto').webcrypto,console,setTimeout:(fn,ms)=>setTimeout(fn,Math.min(ms,10)),clearTimeout,fetch:async(url)=>{calls.push(url);return {ok:true,json:async()=>url.endsWith('config')?{client_id:'123'}:url.endsWith('login')?{session:'test',access_token:'test'}:state}}};
 vm.runInNewContext(source,context);
 await new Promise(r=>setTimeout(r,50));
 const message=element('notice').textContent;
 if(mode==='ok'){assert.equal(message,'Подключено к Discord');assert.deepEqual(calls,['/api/config','/api/login','/api/state'])}
 if(mode==='timeout'){assert.match(message,/15 секунд/);assert.deepEqual(calls,['/api/config'])}
 if(mode==='outside'){assert.match(message,/Нет подключения к окну Discord/);assert.deepEqual(calls,['/api/config'])}
}
(async()=>{for(const mode of ['ok','timeout','outside'])await scenario(mode);console.log('Startup checks passed: success, SDK timeout, outside Discord')})().catch(e=>{console.error(e);process.exitCode=1});
