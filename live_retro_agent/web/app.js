const $ = (q) => document.querySelector(q);
let currentJob = null;

async function health(){
  try{const r=await fetch('/api/health');if(!r.ok)throw new Error();const x=await r.json();$('#health').textContent=x.model_ready?'已连接 · 大模型可用':'已连接 · 检查模型配置';$('#health').classList.add('ok');}
  catch{$('#health').textContent='服务未连接';}
}

function renderStatus(x){
  $('#status-label').textContent=x.status_text||x.status;
  $('#progress-bar').style.width=`${x.progress||0}%`;
  $('#status-message').textContent=x.message||'';
  $('#status-log').textContent=(x.log||[]).join('\n');
  if(x.status==='failed'){$('#status-message').classList.add('error');$('#submit').disabled=false;}
  if(x.status==='completed'){
    $('#result-card').hidden=false;
    $('#result-summary').textContent=x.summary||'分析与文件校验已经完成。';
    $('#downloads').innerHTML=(x.outputs||[]).map((o,i)=>`<a class="${i?'secondary':''}" href="${o.url}">${o.label}</a>`).join('');
    $('#submit').disabled=false;
  }
}

async function poll(){
  if(!currentJob)return;
  try{const r=await fetch(`/api/jobs/${currentJob}`);const x=await r.json();renderStatus(x);if(!['completed','failed'].includes(x.status))setTimeout(poll,1200);}
  catch{setTimeout(poll,2000);}
}

$('#job-form').addEventListener('submit',async(e)=>{
  e.preventDefault();
  $('#submit').disabled=true;$('#result-card').hidden=true;$('#status-card').hidden=false;
  renderStatus({status:'queued',status_text:'正在提交',progress:2,message:'正在复制并检查上传文件',log:[]});
  try{
    const r=await fetch('/api/jobs',{method:'POST',body:new FormData(e.target)});
    const x=await r.json();if(!r.ok)throw new Error(x.error||'提交失败');currentJob=x.job_id;poll();
  }catch(err){renderStatus({status:'failed',status_text:'提交失败',progress:0,message:err.message,log:[]});}
});

health();

