import {defineConfig,loadEnv} from 'vite';
import worker from './worker.js';

export default defineConfig(({mode})=>{
 const config=loadEnv(mode,process.cwd(),'');
 return {plugins:[{name:'dashboard-api',configureServer(server){
  server.middlewares.use('/api/dashboard',async(req,res)=>{
   try{
    const chunks=[];let size=0;
    for await(const chunk of req){size+=chunk.length;if(size>8192){res.writeHead(413,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'Запрос слишком большой.'}));return}chunks.push(chunk)}
    const url='http://'+req.headers.host+'/api/dashboard'+req.url;
    const request=new Request(url,{method:req.method,headers:req.headers,body:['GET','HEAD'].includes(req.method)?undefined:Buffer.concat(chunks)});
    const response=await worker.fetch(request,{BRIDGE_KEY:config.DASHBOARD_BRIDGE_KEY,BOT_ORIGIN:config.BOT_ORIGIN||'https://bot-1794028033-8746-techieskings.bothost.tech'});
    res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
   }catch{res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'Не удалось связаться с сервером бота.'}))}
  });
 }}]};
});
