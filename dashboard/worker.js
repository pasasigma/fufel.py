const endpoints=new Set(['login','logout','me','overview','members','member','channels','audit','accounts','action']);
function secured(response){
 const headers=new Headers(response.headers);
 headers.set('X-Content-Type-Options','nosniff');
 headers.set('Referrer-Policy','same-origin');
 headers.set('X-Frame-Options','DENY');
 headers.set('Permissions-Policy','camera=(), microphone=(), geolocation=()');
 headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: https://cdn.discordapp.com https://media.discordapp.net; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
 return new Response(response.body,{status:response.status,headers});
}
function error(message,status){return secured(Response.json({error:message},{status,headers:{'Cache-Control':'no-store'}}))}
export default {
 async fetch(request,env){
  const url=new URL(request.url);
  if(!url.pathname.startsWith('/api/'))return secured(await env.ASSETS.fetch(request));
  const path=url.pathname.replace('/api/dashboard/','');
  if(!url.pathname.startsWith('/api/dashboard/')||!endpoints.has(path))return error('Раздел не найден.',404);
  if(!['GET','POST'].includes(request.method))return error('Метод недоступен.',405);
  if(request.method==='POST'&&request.headers.get('Origin')!==url.origin)return error('Недопустимый источник запроса.',403);
  if(!env.BRIDGE_KEY||env.BRIDGE_KEY.length<32)return error('Панель ожидает подключения к боту.',503);
  let origin;
  try{origin=new URL(env.BOT_ORIGIN);if(origin.protocol!=='https:'||origin.username||origin.password)throw new Error()}catch{return error('Адрес бота не настроен.',503)}
  let body;
  if(request.method==='POST'){
   if(!request.headers.get('Content-Type')?.startsWith('application/json'))return error('Ожидается JSON.',415);
   if(Number(request.headers.get('Content-Length'))>8192)return error('Запрос слишком большой.',413);
   const reader=request.body?.getReader();let size=0;const chunks=[];
   if(reader){while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>8192){await reader.cancel();return error('Запрос слишком большой.',413)}chunks.push(value)}}
   body=new Uint8Array(size);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength}
  }
  const headers=new Headers({'X-Dashboard-Key':env.BRIDGE_KEY,'X-Dashboard-IP':request.headers.get('CF-Connecting-IP')||'unknown','Accept':'application/json'});
  if(body)headers.set('Content-Type','application/json');
  headers.set('X-CSRF-Token',request.headers.get('X-CSRF-Token')||'');
  const cookie=(request.headers.get('Cookie')||'').split(';').find(c=>c.trim().startsWith('__Host-dashboard='));
  if(cookie)headers.set('Cookie',cookie.trim());
  try{
   const upstream=await fetch(new URL('/dashboard-api/'+path+url.search,origin),{method:request.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(25000)});
   if(upstream.status>=300&&upstream.status<400)return error('Сервер бота перенаправляет запрос. Проверьте адрес.',502);
   const resultHeaders=new Headers({'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
   const setCookie=upstream.headers.get('Set-Cookie');if(setCookie)resultHeaders.set('Set-Cookie',setCookie);
   if(!upstream.headers.get('Content-Type')?.includes('application/json'))return error('Сервер бота ещё не готов к работе панели.',502);
   return secured(new Response(upstream.body,{status:upstream.status,headers:resultHeaders}));
  }catch{return error('Нет ответа от бота. Проверьте журнал перед повтором действия.',502)}
 }
};
