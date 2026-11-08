import {DiscordSDK} from '@discord/embedded-app-sdk';
const $=id=>document.getElementById(id);
const fmt=n=>Number(n).toLocaleString('ru-RU');
let session='', state=null, busy=false, polling=false, retry=null;
let sampledAt=performance.now(),wheelRotation=0,frame=0,lastPoll=0;
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const notice=(text,error=false)=>{$('notice').textContent=text;$('notice').classList.toggle('error',error)};
async function api(path,body){
 const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},...(body?{body:JSON.stringify(body)}:{})});
 let data;try{data=await response.json()}catch{data={error:response.status===401?'Сессия завершилась. Перезапустите Activity.':'Сервер недоступен. Повторите запрос.'}}
 if(!response.ok)throw new Error(data.error||'Не удалось выполнить запрос');return data;
}
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{
 const name=button.dataset.tab;document.querySelectorAll('.screen').forEach(s=>s.hidden=s.id!==name);
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));draw();drawWheel();
}));
function node(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e}
function shops(target,roles){$(target).replaceChildren();roles.forEach(role=>{
 const row=node('div','','role-row'), info=node('div','');info.append(node('strong',role.name),node('small',fmt(role.price)+' монет'));
 const b=node('button',role.owned?'Куплено':'Купить');b.disabled=busy||role.owned||!role.available||state.balance<role.price;
 b.onclick=()=>act('buy',{role:role.id});row.append(info,b);$(target).append(row);
})}
function render(){
 $('admin-tab').hidden=!state.is_admin;
 $('balance').textContent=fmt(state.balance);$('greeting').textContent='Привет, '+state.name;
 shops('mini-shop',state.roles);shops('full-shop',state.roles);
 $('history').replaceChildren();if(!state.history.length)$('history').append(node('p','Пока нет операций. Напиши в чат или зайди в войс.','muted'));
 state.history.forEach(h=>{const row=node('div','','entry'),a=node('div',h.reason);a.append(node('small',new Date(h.created*1000).toLocaleString('ru-RU')));row.append(a,node('strong',(h.delta>0?'+':'')+fmt(h.delta),h.delta>0?'positive':'negative'));$('history').append(row)});
 $('reward-list').replaceChildren();state.prizes.forEach(([kind,value],i)=>{
 const row=node('div','','reward-row');row.append(node('span',kind==='role'?'◆':kind==='coins'?'●':'—','reward-mark'),node('span',prizeLabel(i)));$('reward-list').append(row);
 });
 drawWheel();
 const c=state.crash, flying=c?.status==='flying';
 $('multiplier').textContent=(c?.multiplier||1).toFixed(1)+'×';
 $('flight-status').textContent=flying?'Полёт продолжается':c?.status==='crashed'?'Полёт завершён':c?.status==='cashed'?'Выигрыш: '+fmt(c.payout)+' монет':'Готов к полёту';
 $('cashout').textContent=flying?'Забрать '+fmt(Math.floor(c.stake*c.multiplier)):'Забрать';
 $('cashout').disabled=busy||!flying;$('start').disabled=busy||flying||state.balance<100;$('stake').disabled=busy||flying;$('spin').disabled=busy||state.balance<1000;
 draw();
}
function prizeLabel(index){
 const [kind,value]=state?.prizes[index]||['nothing',0];
 return kind==='role'?(state.roles.find(r=>r.id===value)?.name||'Роль'):kind==='coins'?fmt(value)+' монет':'Без выигрыша';
}
function visualMultiplier(){
 const c=state?.crash;if(!c)return 1;
 if(c.status!=='flying'||reduced.matches)return c.multiplier;
 const age=Math.min(0.8,(performance.now()-sampledAt)/1000);
 return Math.min(10,Math.exp((c.growth_rate||.12)*(c.elapsed+age)));
}
function draw(){
 const canvas=$('chart'),w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
 const dpr=Math.min(2,devicePixelRatio);if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
 const x=canvas.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,w,h);
 const c=state?.crash,m=visualMultiplier(),rate=c?.growth_rate||.12,elapsed=Math.log(Math.max(1,m))/rate;
 const ymax=Math.min(10,Math.max(2,Math.ceil(m*1.25))),tmax=Math.max(10,Math.ceil(elapsed*1.25/5)*5),left=42,top=24,right=w-20,bottom=h-32;
 const px=t=>left+t/tmax*(right-left),py=v=>bottom-(v-1)/(ymax-1)*(bottom-top);
 x.font='12px "Segoe UI",sans-serif';x.lineWidth=1;
 for(let i=0;i<=5;i++){
  const v=1+(ymax-1)*i/5,y=py(v);x.strokeStyle='#303039';x.beginPath();x.moveTo(left,y);x.lineTo(right,y);x.stroke();x.fillStyle='#b4b4c1';x.textAlign='right';x.fillText(v.toFixed(1)+'×',left-8,y+4);
  const t=tmax*i/5,xx=px(t);x.beginPath();x.moveTo(xx,top);x.lineTo(xx,bottom);x.stroke();x.textAlign='center';x.fillText(Math.round(t)+'с',xx,bottom+22);
 }
 const curve=()=>{x.moveTo(left,bottom);for(let i=1;i<=100;i++){const t=elapsed*i/100;x.lineTo(px(t),py(Math.exp(rate*t)))}};
 const won=c?.status==='cashed',lost=c?.status==='crashed',color=won?'#93e6b1':lost?'#ff7385':'#ed3046';
 x.beginPath();curve();x.lineTo(px(elapsed),bottom);x.closePath();const fill=x.createLinearGradient(0,top,0,bottom);fill.addColorStop(0,won?'#93e6b144':'#ed304655');fill.addColorStop(1,won?'#93e6b100':'#ed304600');x.fillStyle=fill;x.fill();
 x.beginPath();curve();x.strokeStyle=color;x.lineWidth=3;x.stroke();x.beginPath();x.arc(px(elapsed),py(m),4,0,Math.PI*2);x.fillStyle=color;x.fill();
 const shown=Math.floor((m+1e-9)*10)/10;
 $('multiplier').textContent=shown.toFixed(1)+'×';$('multiplier').style.color=won?'#93e6b1':lost?'#ff7385':'';
 if(c?.status==='flying')$('cashout').textContent='Забрать ≈ '+fmt(Math.floor(c.stake*shown));
}
function animateChart(){
 if(!document.hidden&&!$('crash').hidden)draw();
 frame=requestAnimationFrame(animateChart);
}
function drawWheel(){
 const canvas=$('wheel');if(!state||!canvas.clientWidth)return;
 const x=canvas.getContext('2d'),size=1000,r=480,n=state.prizes.length*2,step=Math.PI*2/n;
 x.clearRect(0,0,size,size);x.save();x.translate(500,500);
 for(let i=0;i<n;i++){
  const index=i%state.prizes.length,[kind]=state.prizes[index],angle=-Math.PI/2+i*step;
  x.beginPath();x.moveTo(0,0);x.arc(0,0,r,angle,angle+step);x.closePath();x.fillStyle=i%2?'#ed3046':'#09090b';x.fill();x.strokeStyle='#ffffff24';x.lineWidth=2;x.stroke();
  x.save();x.rotate(angle+step/2);x.textAlign='right';x.fillStyle='#fff';x.font='600 23px "Segoe UI",sans-serif';
  let label=prizeLabel(index);while(x.measureText(label).width>285&&label.length>3)label=label.slice(0,-2)+'…';x.fillText(label,r-24,8);x.restore();
 }
 x.beginPath();x.arc(0,0,r,0,Math.PI*2);x.strokeStyle='#ed3046';x.lineWidth=12;x.stroke();x.restore();
}
async function spinWheel(result){
 const count=state.prizes.length,n=count*2,index=Number.isInteger(result.prize_index)?result.prize_index:state.prizes.findIndex(([kind,value])=>kind===result.kind&&value===result.value);
 if(index<0||index>=count)throw new Error('Не удалось показать сектор. Проверь историю баланса.');
 const sector=index+(Math.random()<.5?0:count),step=360/n,target=((360-(sector+.5)*step)%360+360)%360;
 const end=wheelRotation+1800+((target-wheelRotation%360+360)%360);
 $('prize').textContent='Колесо вращается…';$('wheel').style.willChange='transform';
 const animation=$('wheel').animate([{transform:'rotate('+wheelRotation+'deg)'},{transform:'rotate('+end+'deg)'}],{duration:reduced.matches?150:4400,easing:'cubic-bezier(.12,.72,.12,1)',fill:'forwards'});
 try{await animation.finished}finally{$('wheel').style.transform='rotate('+end+'deg)';animation.cancel();$('wheel').style.willChange='auto';wheelRotation=end}
 $('prize').textContent=result.kind==='coins'?'Выигрыш: '+fmt(result.value)+' монет':result.kind==='role'?'Выигрыш: '+prizeLabel(index):'В этот раз без выигрыша';
 $('prize').classList.remove('result-ready');void $('prize').offsetWidth;$('prize').classList.add('result-ready');
}
async function refresh(){state=await api('state');sampledAt=performance.now();render();if(state.pending_roles)notice('Роль оплачена и ожидает выдачи. Администратору нужно проверить права бота.',true)}
async function act(action,extra={}){
 if(busy)return;busy=true;render();
 const signature=JSON.stringify({action,...extra});
 const key=retry?.signature===signature?retry.key:crypto.randomUUID();retry={signature,key};
 try{
  const result=await api('action',{action,key,...extra});retry=null;
  if(action==='roulette')await spinWheel(result);
  notice(result.error|| (action==='buy'?'Роль приобретена':action==='cashout'?'Результат полёта сохранён':'Готово'),Boolean(result.error));
  await refresh();
 }catch(error){notice(error.message,true)}finally{busy=false;if(state)render()}
}
$('start').onclick=()=>act('start',{stake:Number($('stake').value)});
$('cashout').onclick=()=>act('cashout');$('spin').onclick=()=>act('roulette');
window.addEventListener('resize',()=>{draw();drawWheel()});
async function init(){
 if(location.protocol==='file:'){notice('Локальный просмотр. Игры, баланс и магазин работают после запуска приложения через Discord.');return}
 try{
  const config=await api('config');const sdk=new DiscordSDK(config.client_id);await sdk.ready();
  if(!sdk.guildId)throw new Error('Открой Activity на сервере, где установлен Фуфлыжник.');
  const {code}=await sdk.commands.authorize({client_id:config.client_id,response_type:'code',state:crypto.randomUUID(),prompt:'none',scope:['identify']});
  const auth=await api('login',{code,guild_id:sdk.guildId});session=auth.session;
  await sdk.commands.authenticate({access_token:auth.access_token});await refresh();notice('Подключено к Discord');
  setInterval(async()=>{const now=performance.now(),delay=state?.crash?.status==='flying'?500:2500;if(polling||busy||document.hidden||now-lastPoll<delay)return;lastPoll=now;polling=true;try{await refresh()}catch(e){notice(e.message,true)}finally{polling=false}},250);
 }catch(error){notice(error.message+' Открой приложение через Discord и проверь настройки Activity.',true)}
}
draw();animateChart();init();

let adminBusy=false,adminRetry=null;
async function adminRequest(operation){
 if(adminBusy||!state?.is_admin)return;
 const target=$('admin-target').value.trim(),amount=Number($('admin-amount').value),reason=$('admin-reason').value.trim();
 if(!/^[0-9]{15,20}$/.test(target)){notice('Введите корректный Discord ID.',true);return}
 if(operation!=='view'&&(!Number.isSafeInteger(amount)||amount<0||amount>1000000000||!reason)){notice('Укажите целую сумму от 0 до 1 000 000 000 и причину.',true);return}
 if(operation==='set'&&!window.confirm('Заменить весь баланс участника '+target+' на '+fmt(amount)+' монет?'))return;
 const signature=JSON.stringify({target,operation,amount,reason});
 const key=adminRetry?.signature===signature?adminRetry.key:crypto.randomUUID();
 if(operation!=='view')adminRetry={signature,key};
 adminBusy=true;document.querySelectorAll('#admin button,#admin input').forEach(e=>e.disabled=true);
 try{
  const result=await api('admin',{target,operation,amount,reason,key});
  if(operation!=='view')adminRetry=null;
  $('admin-result').textContent=result.name+' · '+result.target+' · Баланс: '+fmt(result.balance)+' монет';
  $('admin-history').replaceChildren();
  if(!result.history.length)$('admin-history').append(node('p','Изменений администраторов пока нет.','muted'));
  result.history.forEach(h=>{const row=node('div','','entry');row.append(node('div',new Date(h.created*1000).toLocaleString('ru-RU')+' · Админ '+h.actor+' · '+h.reason),node('strong',fmt(h.before_balance)+' → '+fmt(h.after_balance)));$('admin-history').append(row)});
  notice(operation==='view'?'Баланс загружен':'Изменение сохранено');await refresh();
 }catch(e){notice(e.message,true)}finally{adminBusy=false;document.querySelectorAll('#admin button,#admin input').forEach(e=>e.disabled=false)}
}
$('admin-form').onsubmit=e=>{e.preventDefault();adminRequest('view')};
document.querySelectorAll('[data-admin-operation]').forEach(b=>b.onclick=()=>adminRequest(b.dataset.adminOperation));
