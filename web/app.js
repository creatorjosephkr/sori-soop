let cancelling=false;
let state, mode='bgm', dirty=false;
let jobHistory=[];
const durationOverrides={};
let durationDraft=false;
function songAutoDuration(){return mode==='song'&&$('song-duration-mode').value==='auto';}
function renderDurationInput(){
    const input=$('seconds-number'),slider=$('seconds');
    if(input.max!==slider.max||input.dataset.mode!==mode)durationDraft=false;
    input.min=slider.min;input.max=slider.max;input.dataset.mode=mode;
    if(!durationDraft)input.value=slider.value;
    const valid=input.value!==''&&input.validity.valid;
    input.setAttribute('aria-invalid',String(!valid));
    $('duration-error').textContent=valid?'':`음악 길이를 ${input.min}~${input.max}초 사이의 정수로 입력하세요.`;
}

function updatePromptCount(){const count=Array.from($('prompt').value).length;setText('prompt-character-count',count.toLocaleString('ko-KR')+' / 2,000자 · 공백·줄바꿈 포함');$('prompt-character-count').classList.toggle('over-limit',count>2000);}
function setText(id,text){if($(id).textContent!==text)$(id).textContent=text;}
function renderGuidance(){
    if(songAutoDuration()){setText('guidance','자동 길이 · 가사와 음악 설명을 바탕으로 모델이 노래 길이를 정합니다. 지원 범위는 10~600초이며, 긴 가사는 더 많은 메모리와 시간이 필요합니다. 처음에는 짧은 가사부터 시작하세요.');return;}
    const rec=recommendation();
    const samples=jobHistory.filter(j=>j.status==='completed'&&!j.includedDownload&&j.settings.mode===mode&&j.settings.backend===$('backend').value&&j.settings.model===$('model').value&&j.settings.seconds===+$('seconds').value&&Number.isFinite(j.elapsedSeconds));
    const base=`이 기기의 초기 권장 길이는 ${rec.seconds}초입니다. 한 번에 한 곡씩 생성합니다.`;
    let timing='선택한 길이의 측정 기록이 아직 없습니다. 생성 후 실제 처리 시간을 안내합니다.';
    if(samples.length){
        const times=samples.map(j=>j.elapsedSeconds);
        timing=`선택한 길이의 실측 ${samples.length}회: 약 ${Math.min(...times)}~${Math.max(...times)}초. 현재 부하에 따라 달라집니다.`;
    }
    setText('guidance',base+'\n\n'+timing);
}
const $=id=>document.getElementById(id);
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,body){const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw Error(data.error||'요청에 실패했습니다.');return data;}
function recommendation(){const s=state.system;const low=(s.ramGB||0)<12||(s.availableGB!==null&&s.availableGB<4);return {model:mode==='song'?'ace-step':'small-music',backend:s.appleSilicon?'apple':'cpu',seconds:(low||mode==='song')?30:60};}
function applyRecommendation(){const r=recommendation();for(const k of ['model','backend'])$(k).value=r[k];$('seconds').max=state.models[r.model].maxSeconds;$('seconds').value=durationOverrides[mode]??r.seconds;}
function render(){if(!state)return;const auto=$('policy').value==='auto';for(const k of ['model','backend'])$(k).disabled=auto;$('seconds').disabled=false;$('bgm').classList.toggle('selected',mode==='bgm');$('song').classList.toggle('selected',mode==='song');$('lyrics-wrap').hidden=mode!=='song';window.MusicPresets?.setMode(mode);const m=state.models[$('model').value];$('seconds').max=m.maxSeconds;if(+$('seconds').value>m.maxSeconds)$('seconds').value=m.maxSeconds;renderDurationInput();$('length').textContent=$('seconds').value+'초';$('max').textContent='모델 최대 '+m.maxSeconds+'초';const r=recommendation();$('basis').textContent='사양 기반 · 실측 전';renderGuidance();const warnings=[];if(!songAutoDuration()&&+$('seconds').value>r.seconds)warnings.push('초기 권장 길이를 초과했습니다. 메모리 부족이나 처리 지연 가능성을 실기기에서 확인해야 합니다.');if(mode==='song')warnings.push(songAutoDuration()?'긴 가사일수록 노래와 생성 시간이 길어질 수 있습니다. 짧은 가사부터 시작하세요.':'가사를 직접 입력하고 짧은 노래부터 시작하세요. '+(state.system.ramGB<12?'8GB급 환경에서는 안정적인 실행을 보장할 수 없습니다.':'30~60초부터 실제 실행 검증이 필요합니다.'));if(mode==='song'&&!songAutoDuration()&&$('lyrics').value.replace(/\[[^\]]*\]/g,'').replace(/\s/g,'').length>+$('seconds').value*4)warnings.push('현재 길이에 비해 가사가 많습니다. 일부 가사가 생략될 수 있으니 자동 길이를 선택하거나 길이를 늘려 주세요.');if(mode==='song'&&!m.vocals)warnings.push('선택한 모델은 가사 기반 노래를 지원하지 않습니다. ACE-Step을 선택하세요.');if($('backend').value==='apple'&&!state.system.appleSilicon)warnings.push('Apple Silicon이 감지되지 않았습니다. CPU 실행 방식을 선택하세요.');if(state.system.availableGB!==null&&state.system.availableGB<3)warnings.push('가용 메모리가 적습니다. 다른 앱을 종료하고 다시 진단하세요.');const warningHTML=warnings.map(w=>`<div class="warning">${escapeHTML(w)}</div>`).join('');if($('warnings').innerHTML!==warningHTML)$('warnings').innerHTML=warningHTML;$('save').disabled=false;}
async function refresh(initial=false){try{$('refresh').disabled=true;const next=await api('/api/status');state=next;if(initial){mode=next.settings.mode;$('song-duration-mode').value=next.settings.durationMode==='auto'?'auto':'manual';$('peak-db').value=next.settings.peakDb??-6;if(Number.isInteger(next.settings.seconds))durationOverrides[mode]=next.settings.seconds;$('policy').value=next.settings.policy;if(next.settings.policy==='auto')applyRecommendation();else for(const k of ['model','backend','seconds']){if(k==='seconds')$('seconds').max=next.models[$('model').value].maxSeconds;if(next.settings[k]!==undefined)$(k).value=next.settings[k];}}else if($('policy').value==='auto')applyRecommendation();const s=state.system;const rows=[['시스템',s.os],['프로세서',s.chip],['전체 메모리',s.ramGB===null?'확인 불가':s.ramGB+' GB'],['현재 가용량 ≈',s.availableGB===null?'확인 불가':s.availableGB+' GB'],['그래픽',s.appleSilicon?'Apple 통합 그래픽':s.gpu.map(g=>g.name+' / '+g.vramGB+' GB').join(', ')||'NVIDIA 미감지 · 기타 GPU 미확인'],['여유 저장 공간',s.diskFreeGB+' GB']];$('system').innerHTML=rows.map(([k,v])=>`<div class="metric"><span>${escapeHTML(k)}</span><b>${escapeHTML(v).replace(/(\d+(?:\.\d+)?) GB/g,'$1&nbsp;GB')}</b></div>`).join('');render();if(!initial)$('message').textContent='진단을 갱신했습니다. 직접 설정과 고정값은 유지됩니다.';}catch(e){$('message').textContent=e.message;}finally{$('refresh').disabled=false;}}
for(const id of ['bgm','song'])$(id).onclick=()=>{if(!state)return;mode=id;dirty=true;if($('policy').value!=='manual')applyRecommendation();render();};
$('policy').onchange=()=>{if(!state)return;if($('policy').value!=='manual')applyRecommendation();dirty=true;render();};
$('song-duration-mode').onchange=()=>{dirty=true;render();};
for(const id of ['model','backend'])$(id).oninput=()=>{dirty=true;render();};
$('seconds').oninput=()=>{durationDraft=false;durationOverrides[mode]=+$('seconds').value;dirty=true;render();};
$('seconds-number').oninput=()=>{
    const input=$('seconds-number');durationDraft=true;dirty=true;
    if(input.value!==''&&input.validity.valid){$('seconds').value=input.value;durationOverrides[mode]=+$('seconds').value;}
    render();
};
$('refresh').onclick=()=>refresh();
$('save').onclick=async()=>{if(!state)return;try{await api('/api/settings',selectedSettings());dirty=false;$('message').textContent='설정을 저장했습니다. 다음 실행에도 유지됩니다.';}catch(e){$('message').textContent=e.message;}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
refresh(true);

function selectedSettings(){const duration=$('seconds-number');if(!songAutoDuration()&&(duration.value===''||!duration.checkValidity())){duration.focus();duration.reportValidity();throw Error(`음악 길이를 ${duration.min}~${duration.max}초 사이의 정수로 입력하세요.`);}if($('peak-db').value.trim()===''||!$('peak-db').checkValidity())throw Error('최대 게인은 -24~0dB 범위로 설정하세요.');return {peakDb:Number($('peak-db').value),policy:$('policy').value,mode,model:$('model').value,backend:$('backend').value,seconds:songAutoDuration()?null:+$('seconds').value,...(mode==='song'?{durationMode:$('song-duration-mode').value}:{})};}
const generateButton=document.querySelector('.generate');
let submitting=false, activeJob=false;
$('lyrics').addEventListener('input',()=>render());
$('prompt').addEventListener('input',updatePromptCount);
updatePromptCount();
$('peak-db').oninput=()=>{dirty=true;};
const originalRender=render;
render=function(){originalRender();updatePromptCount();generateButton.classList.toggle('is-generating',submitting||activeJob);$('song-duration-mode-wrap').hidden=mode!=='song';$('manual-duration-controls').hidden=songAutoDuration();$('auto-duration-help').hidden=!songAutoDuration();$('seconds').disabled=songAutoDuration();$('seconds-number').disabled=songAutoDuration();$('generation-status').classList.toggle('is-generating',submitting||activeJob);$('cancel-generation').hidden=!activeJob;$('cancel-generation').disabled=cancelling;$('cancel-generation').innerHTML=window.StudioIcons('stop')+' <span>'+(cancelling?'중단 요청 중…':'생성 중단')+'</span>';if(!state)return;setText('prompt-limit-help',mode==='song'?'음악 설명은 최대 2,000자까지 입력할 수 있습니다. 번역 후 음악 설명·내부 지시문을 포함해 엔진 한도인 256토큰을 검사합니다. 초과하면 줄일 수 있도록 안내하며 자동으로 자르지 않습니다.':'음악 설명은 최대 2,000자까지 입력할 수 있습니다.');setText('prompt-language-help',state.translationReady?'한글로 입력한 음악 설명은 내 컴퓨터에서 영어로 자동 변환해 생성에 사용합니다. 제목과 가사는 원문을 유지합니다.':'한글 자동 번역 모델이 준비되지 않았습니다. 영어 설명이나 프리셋을 사용해 주세요.');const supported=(mode==='bgm'&&$('model').value==='small-music'&&state.engines[$('backend').value])||(mode==='song'&&$('model').value==='ace-step'&&state.songEngines?.[$('backend').value]);generateButton.disabled=!supported||submitting||activeJob;const buttonLabel=(submitting||activeJob)?'생성 중…':(mode==='song'?'노래 만들기':'배경음악 만들기');const buttonHTML=window.StudioIcons((submitting||activeJob)||mode==='song'?'music':'sparkles')+' <span>'+buttonLabel+'</span>';if(generateButton.innerHTML!==buttonHTML)generateButton.innerHTML=buttonHTML;$('new-track').setAttribute('aria-label',mode==='song'?'노래 새로 만들기':'배경음악 새로 만들기');document.querySelector('.composer>.footnote').textContent=mode==='song'?'ACE-Step · 입력한 가사로 보컬과 반주를 함께 생성합니다. 첫 생성은 모델 준비 시간이 포함됩니다.':(state.translationReady?'Small-Music 배경음악 생성 · 한글·영어 설명과 프리셋을 사용할 수 있습니다.':'Small-Music 배경음악 생성 · 영어 설명 또는 프리셋을 사용해 주세요.');document.querySelector('label[for="prompt"]').textContent=mode==='song'?'곡의 장르와 분위기를 설명해 주세요':'떠오르는 음악을 설명해 주세요';};
generateButton.onclick=async()=>{submitting=true;render();$('generation-status').textContent='생성 요청을 보내고 있습니다…';try{const created=await api('/api/generate',{settings:selectedSettings(),title:$('track-title').value,prompt:$('prompt').value,lyrics:$('lyrics').value,language:$('language').value});resultPages[created.settings.mode]=1;selectResultTab(created.settings.mode);$('message').textContent='생성을 시작했습니다. 다른 작업은 완료 후 시작할 수 있습니다.';await jobs();$('results').scrollIntoView({block:'start',behavior:'instant'});}catch(e){$('message').textContent=e.message;$('generation-status').textContent=e.message;}finally{submitting=false;render();}};
$('cancel-generation').onclick=async()=>{if(cancelling)return;cancelling=true;render();try{await api('/api/cancel',{});$('message').textContent='생성 중단을 요청했습니다.';await jobs();}catch(e){$('message').textContent=e.message;}finally{cancelling=false;render();}};
const statusLabels={queued:'대기 중',running:'생성 중',completed:'완료',cancelled:'취소됨',failed:'실패',interrupted:'중단됨'};
let jobsSignature='';
let resultMode=localStorage.getItem('music-result-tab')==='song'?'song':'bgm';
const RESULTS_PER_PAGE=5;
const resultPages={bgm:1,song:1};
let paginationSignature='';
function selectResultTab(value){
    resultMode=value;localStorage.setItem('music-result-tab',value);
    for(const key of ['bgm','song']){
        const tab=$('results-'+key);
        tab.classList.toggle('selected',key===value);
        tab.setAttribute('aria-selected',String(key===value));
        tab.tabIndex=key===value?0:-1;
    }
    $('jobs').setAttribute('aria-labelledby','results-'+value);
}
for(const key of ['bgm','song']){
    $('results-'+key).onclick=()=>{selectResultTab(key);jobs();};
    $('results-'+key).onkeydown=event=>{
        if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
        event.preventDefault();
        const next=event.key==='Home'?'bgm':event.key==='End'?'song':resultMode==='bgm'?'song':'bgm';
        selectResultTab(next);$('results-'+next).focus();jobs();
    };
}
selectResultTab(resultMode);
const resultSignatures=new Map();
const expandedResults=new Set();
function renderResultPage(allItems){
    const total=allItems.length;
    const pages=Math.max(1,Math.ceil(total/RESULTS_PER_PAGE));
    const page=Math.max(1,Math.min(resultPages[resultMode],pages));
    resultPages[resultMode]=page;
    const items=allItems.slice((page-1)*RESULTS_PER_PAGE,page*RESULTS_PER_PAGE);
    const signature=JSON.stringify([resultMode,page,items]);
    if(signature!==jobsSignature){jobsSignature=signature;updateResultList(items);}
    $('result-pagination').hidden=total===0;
    setText('pagination-info',`전체 ${total}개 · ${page} / ${pages} 페이지`);
    const numbers=[...new Set([1,pages,page-2,page-1,page,page+1,page+2].filter(n=>n>=1&&n<=pages))].sort((a,b)=>a-b);
    let buttons=`<button type="button" data-page="${page-1}" ${page===1?'disabled':''} aria-label="이전 페이지">이전</button>`;
    numbers.forEach((number,index)=>{
        if(index&&number>numbers[index-1]+1)buttons+='<span class="page-gap" aria-hidden="true">…</span>';
        buttons+=`<button type="button" data-page="${number}" aria-label="${number} 페이지" ${number===page?'aria-current="page"':''}>${number}</button>`;
    });
    buttons+=`<button type="button" data-page="${page+1}" ${page===pages?'disabled':''} aria-label="다음 페이지">다음</button>`;
    const pagerSignature=JSON.stringify([resultMode,total,page,pages]);
    if(paginationSignature!==pagerSignature){paginationSignature=pagerSignature;$('pagination-buttons').innerHTML=buttons;}
}
$('pagination-buttons').addEventListener('click',event=>{
    const button=event.target.closest('[data-page]');
    if(!button||button.disabled)return;
    const page=Number(button.dataset.page);
    if(!Number.isInteger(page)||page<1||page===resultPages[resultMode])return;
    resultPages[resultMode]=page;
    renderResultPage(jobHistory.filter(job=>(job.settings.mode||'bgm')===resultMode));
    $('results-'+resultMode).focus({preventScroll:true});
    $('results').scrollIntoView({block:'start',behavior:'instant'});
});
function musicTime(value){const seconds=Math.max(0,Math.floor(Number(value)||0));return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
function durationText(job){if(Number.isFinite(job.durationSeconds))return musicTime(job.durationSeconds);return job.settings.durationMode==='auto'?'자동 · 가사 기준':musicTime(job.settings.seconds);}
function resultMarkup(job){
    const settings=job.settings;
    const pending=['queued','running'].includes(job.status);
    const title=job.title?.trim()||(job.title===undefined?job.prompt:'')||(settings.mode==='song'?'보컬 노래':'배경음악');
    const filename=(job.title?.trim()||('music-'+job.id)).replace(/[\\/:*?"<>|\x00-\x1f]/g,'-').replace(/[. ]+$/,'').slice(0,80)||('music-'+job.id);
    const date=new Date(job.createdAt*1000).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const language=({ko:'한국어',en:'영어',ja:'일본어',zh:'중국어',unknown:'기타 언어'})[job.language]||job.language;
    const info=[['모델',state?.models[settings.model]?.name||settings.model],['실행 방식',settings.backend==='apple'?'Apple Silicon':'CPU'],['음악 길이',durationText(job)]];
    if(language)info.push(['보컬 언어',language]);
    if(settings.peakDb!==undefined)info.push(['최대 게인',settings.peakDb+'dB']);
    if(Number.isFinite(job.outputPeakDb))info.push(['실제 피크',job.outputPeakDb.toFixed(1)+'dB']);
    if(Number.isFinite(job.elapsedSeconds))info.push(['처리 시간',job.elapsedSeconds+'초']);
    if(job.processPeakGB)info.push(['프로세스 최고 메모리',job.processPeakGB+'GB']);
    if(job.enginePeakGB)info.push(['엔진 최고 메모리',job.enginePeakGB+'GB']);
    return `<details id="result-${escapeHTML(job.id)}" data-job-id="${escapeHTML(job.id)}" class="notice result-item result-disclosure ${escapeHTML(job.status)}">
      <summary class="result-summary">${pending?`<span class="result-loading" role="status" aria-label="${job.status==='queued'?'생성 대기 중':'음악 생성 중'}">${window.StudioIcons('spinner')}</span>`:`<button type="button" class="result-play" data-play="${escapeHTML(job.id)}" aria-label="${job.audioUrl?'재생':'생성 완료 후 재생 가능'}" title="${job.audioUrl?'펼쳐서 재생':'생성 완료 후 재생 가능'}" aria-pressed="false" ${job.audioUrl?'':'disabled'}><span aria-hidden="true">${window.StudioIcons('play')}</span></button>`}<span class="result-summary-main"><span class="result-summary-title">${escapeHTML(title)}</span><span class="result-summary-meta"><span class="result-state ${escapeHTML(job.status)}">${escapeHTML(statusLabels[job.status]||job.status)}</span><span>${escapeHTML(durationText(job))}</span><span>${escapeHTML(date)}</span></span></span><span class="result-chevron" aria-hidden="true">${window.StudioIcons('chevron')}</span></summary>
      <div class="result-body"><p class="playback-message" role="status" aria-live="polite"></p>
        <form class="result-title-editor" hidden><label>제목<input class="track-title" name="title" type="text" maxlength="100" required autocomplete="off"></label><div class="title-editor-actions"><button type="submit">저장</button><button type="button" data-rename-cancel>취소</button></div></form><p class="rename-message" role="status" aria-live="polite"></p>
        ${job.audioUrl?window.AudioSpectrum.markup(escapeHTML(job.audioUrl)):''}
        ${job.phase?`<p class="job-phase">${escapeHTML(job.phase)}</p>`:''}
        ${job.error?`<p class="warning">${escapeHTML(job.error)}</p>${job.errorDetails?`<details class="result-error"><summary>오류 상세</summary><p>${escapeHTML(job.errorDetails)}</p></details>`:''}`:''}
        <h3>음악 설명</h3><p class="result-description">${escapeHTML(job.prompt||'')}</p>
        ${job.generationPrompt?`<details class="result-translation"><summary>생성에 사용한 영어 설명</summary><p>${escapeHTML(job.generationPrompt)}</p></details>`:''}
        ${job.lyrics?`<section class="saved-lyrics"><h3>가사${language?' · '+escapeHTML(language):''}</h3><pre>${escapeHTML(job.lyrics)}</pre></section>`:''}
        <details class="result-technical"><summary>생성 설정 및 처리 정보</summary><dl>${info.map(([key,value])=>`<div><dt>${escapeHTML(key)}</dt><dd>${escapeHTML(value)}</dd></div>`).join('')}</dl></details>
        <div class="result-actions"><button type="button" class="rename-result" data-rename ${['running','queued'].includes(job.status)?'disabled':''}>제목 수정</button>${job.audioUrl?`<a class="download-result" href="${escapeHTML(job.audioUrl)}" download="${escapeHTML(filename)}.wav">WAV 다운로드</a>`:''}<button class="delete-result" data-delete="${escapeHTML(job.id)}" ${['running','queued'].includes(job.status)?'disabled':''}>삭제</button></div>
      </div>
    </details>`;
}
function updateResultList(items){
    const list=$('jobs');
    const wanted=new Set(items.map(job=>'result-'+job.id));
    for(const node of [...list.children]){
        if(!wanted.has(node.id)){window.AudioSpectrum?.release(node);node.querySelector('audio')?.pause();node.remove();resultSignatures.delete(node.id);}
    }
    if(!items.length){
        const message=document.createElement('p');message.className='empty-results';
        message.textContent=resultMode==='song'?'가사를 입력하고 노래를 생성하면 여기에 표시됩니다.':'배경음악을 생성하면 여기에 표시됩니다.';
        list.append(message);return;
    }
    items.forEach((job,index)=>{
        const id='result-'+job.id,signature=JSON.stringify(job);
        let node=document.getElementById(id);
        const previous=resultSignatures.has(id)?JSON.parse(resultSignatures.get(id)):null;
        if(node&&previous&&previous.title!==job.title&&JSON.stringify({...previous,title:job.title})===signature){
            // A title change must retain the existing audio element and playback position.
            const template=document.createElement('template');template.innerHTML=resultMarkup(job).trim();
            node.querySelector('.result-summary-title').textContent=template.content.querySelector('.result-summary-title').textContent;
            const link=node.querySelector('.download-result');
            if(link)link.download=template.content.querySelector('.download-result').download;
            resultSignatures.set(id,signature);
        }
        if(!node||resultSignatures.get(id)!==signature){
            const template=document.createElement('template');template.innerHTML=resultMarkup(job).trim();
            const next=template.content.firstElementChild;
            next.open=node?.open??expandedResults.has(job.id);
            if(node?.querySelector('.result-technical')?.open)next.querySelector('.result-technical').open=true;
            if(node){window.AudioSpectrum?.release(node);node.querySelector('audio')?.pause();node.replaceWith(next);}
            node=next;resultSignatures.set(id,signature);
        }
        if(list.children[index]!==node)list.insertBefore(node,list.children[index]||null);
        window.AudioSpectrum?.attach(node);
    });
}
function syncPlayButton(audio){
    const buttons=audio.closest('.result-disclosure')?.querySelectorAll('[data-play]');
    if(!buttons)return;
    const playing=!audio.paused&&!audio.ended;
    for(const button of buttons){
        button.classList.toggle('is-playing',playing);
        button.setAttribute('aria-pressed',String(playing));
        button.setAttribute('aria-label',playing?'일시정지':'재생');
        button.title=playing?'일시정지':'펼쳐서 재생';
        button.querySelector('span').innerHTML=window.StudioIcons(playing?'pause':'play');
    }
}
$('jobs').addEventListener('click',event=>{
    const button=event.target.closest('[data-rename],[data-rename-cancel]');
    if(!button||button.disabled)return;
    const card=button.closest('.result-disclosure'),form=card.querySelector('.result-title-editor');
    card.querySelector('.rename-message').textContent='';
    if(button.hasAttribute('data-rename-cancel')){
        form.hidden=true;card.querySelector('[data-rename]').focus({preventScroll:true});return;
    }
    const job=jobHistory.find(job=>job.id===card.dataset.jobId);
    form.elements.title.value=(job.title??job.prompt??'').slice(0,100);
    form.hidden=false;form.elements.title.focus();form.elements.title.select();
});
$('jobs').addEventListener('keydown',event=>{
    if(event.key==='Escape'&&event.target.closest('.result-title-editor')){
        event.preventDefault();event.target.closest('.result-title-editor').querySelector('[data-rename-cancel]').click();
    }
});
$('jobs').addEventListener('submit',async event=>{
    const form=event.target.closest('.result-title-editor');if(!form)return;
    event.preventDefault();
    const card=form.closest('.result-disclosure'),message=card.querySelector('.rename-message');
    const controls=[...form.querySelectorAll('input,button')];
    const title=form.elements.title.value.trim();
    if(!title){message.textContent='제목을 1~100자로 입력하세요.';form.elements.title.focus();return;}
    controls.forEach(control=>control.disabled=true);message.textContent='제목을 저장하고 있습니다…';
    try{
        const updated=await api('/api/rename',{id:card.dataset.jobId,title});
        jobHistory=jobHistory.map(job=>job.id===updated.id?updated:job);
        renderResultPage(jobHistory.filter(job=>(job.settings.mode||'bgm')===resultMode));
        form.hidden=true;message.textContent='제목을 저장했습니다.';
        card.querySelector('[data-rename]').focus({preventScroll:true});
    }catch(error){message.textContent=error.message;}
    finally{controls.forEach(control=>control.disabled=false);}
});
for(const type of ['play','pause','ended','error'])$('jobs').addEventListener(type,event=>{
    const audio=event.target;
    if(!audio.matches('audio'))return;
    if(type==='play'&&!audio.paused&&!audio.ended){
        for(const other of $('jobs').querySelectorAll('audio'))if(other!==audio)other.pause();
        audio.closest('.result-disclosure').querySelector('.playback-message').textContent='';
    }
    if(type==='error')audio.closest('.result-disclosure').querySelector('.playback-message').textContent='음악 파일을 불러올 수 없습니다. 다시 시도해 주세요.';
    syncPlayButton(audio);
},true);
$('jobs').addEventListener('click',async event=>{
    const button=event.target.closest('[data-play]');
    if(!button||button.disabled)return;
    event.preventDefault();event.stopPropagation();
    const card=button.closest('.result-disclosure'),audio=card.querySelector('audio');
    if(!audio)return;
    card.open=true;expandedResults.add(card.dataset.jobId);
    const message=card.querySelector('.playback-message');message.textContent='';
    try{
        if(audio.paused||audio.ended){
            for(const other of $('jobs').querySelectorAll('audio'))if(other!==audio)other.pause();
            window.AudioSpectrum?.prepare(audio);
            await audio.play();
        }else{
            audio.pause();
            if(button.classList.contains('result-play')){card.open=false;expandedResults.delete(card.dataset.jobId);}
        }
    }catch(error){
        if(error.name!=='AbortError')message.textContent='음악을 재생할 수 없습니다. 재생기를 눌러 다시 시도해 주세요.';
    }
    syncPlayButton(audio);
});
$('jobs').addEventListener('toggle',event=>{
    const item=event.target;
    if(!item.matches('.result-disclosure')||!item.isConnected)return;
    if(item.open)expandedResults.add(item.dataset.jobId);else expandedResults.delete(item.dataset.jobId);
},true);
async function jobs(){try{const data=await api('/api/jobs');jobHistory=data.jobs;activeJob=data.jobs.some(j=>['queued','running'].includes(j.status));const visibleJobs=data.jobs.filter(j=>(j.settings.mode||'bgm')===resultMode);for(const key of ['bgm','song'])$('count-'+key).textContent=data.jobs.filter(j=>(j.settings.mode||'bgm')===key).length;const latest=visibleJobs[0];const running=data.jobs.find(j=>['queued','running'].includes(j.status));const kind=resultMode==='bgm'?'배경음악':'보컬 노래';$('generation-status').textContent=running?`${running.phase||((running.settings.mode==='song'?'보컬 노래':'배경음악')+' 생성 중')} · ${Math.max(0,Math.floor(Date.now()/1000-running.createdAt))}초 경과`:latest?`${kind} 최근 작업: ${statusLabels[latest.status]||latest.status} · 총 ${visibleJobs.length}개`:`아직 생성한 ${kind} 결과가 없습니다.`;render();renderResultPage(visibleJobs);}catch(e){$('message').textContent=e.message;}}
setInterval(jobs,2000);jobs();
$('new-track').onclick=()=>{resetDraftInputs();$('lyric-tools-status').textContent='';$('lyric-request-fallback').value='';$('lyric-request-fallback').hidden=true;$('message').textContent='새 '+(mode==='song'?'노래':'배경음악')+'를 만들 준비가 되었습니다.';updatePromptCount();$('track-title').focus();};

const benchmarkButton=document.createElement('button');benchmarkButton.className='save';benchmarkButton.textContent='성능 측정 · 20초 배경음악';
document.querySelector('.sidebar-tip').append(benchmarkButton);
benchmarkButton.onclick=async()=>{if(!state)return;submitting=true;render();benchmarkButton.disabled=true;$('generation-status').textContent='성능 측정을 시작하고 있습니다…';try{await api('/api/generate',{settings:{policy:'manual',mode:'bgm',model:'small-music',backend:$('backend').value,seconds:20,peakDb:selectedSettings().peakDb},prompt:'Warm instrumental piano music with soft drums, no vocals.'});resultPages.bgm=1;selectResultTab('bgm');$('message').textContent='20초 음악을 생성해 처리 시간을 측정합니다. 첫 실행은 초기화 시간이 포함됩니다.';await jobs();$('results').scrollIntoView({block:'start',behavior:'instant'});}catch(e){$('message').textContent=e.message;}finally{submitting=false;benchmarkButton.disabled=false;render();}};
function resetDraftInputs(){
    $('track-title').value='';$('prompt').value='';$('lyrics').value='';window.MusicPresets?.reset();updatePromptCount();
    localStorage.removeItem('music-prompt');localStorage.removeItem('music-lyrics');
}
resetDraftInputs();
// Clear browser-restored form values after a fresh load as well.
window.addEventListener('pageshow',event=>{if(!event.persisted)resetDraftInputs();});

$('jobs').addEventListener('click',async event=>{
    const button=event.target.closest('[data-delete]');
    if(!button||button.disabled)return;
    button.disabled=true;button.textContent='삭제 중…';
    try{
        await api('/api/delete',{id:button.dataset.delete});
        await jobs();
        $('message').textContent='결과를 삭제했습니다. 파일은 로컬 휴지통에 보관됩니다.';
    }catch(e){
        $('message').textContent=e.message;
        button.disabled=false;button.textContent='삭제';
    }
});

$('language').value=localStorage.getItem('music-language')||'ko';
$('language').onchange=()=>localStorage.setItem('music-language',$('language').value);
$('lyrics-example').onclick=()=>{
    $('lyrics').value='[Verse]\n창가에 내려앉은 따스한 햇살\n잠들었던 마음이 천천히 깨어나\n\n[Chorus]\n오늘도 너와 함께 걸어가\n작은 꿈을 품고 노래해';
    $('language').value='ko';
    localStorage.setItem('music-language','ko');
};
$('copy-lyric-request').onclick=async()=>{
    const language=$('language').selectedOptions[0]?.textContent||'한국어';
    const description=$('prompt').value.trim();
    const title=$('track-title').value.trim();
    const duration=$('seconds-number');
    if(!songAutoDuration()&&(duration.value===''||!duration.checkValidity())){
        $('lyric-tools-status').textContent=`곡 길이를 ${duration.min}~${duration.max}초 사이의 정수로 입력해 주세요.`;
        duration.focus();duration.reportValidity();return;
    }
    const seconds=songAutoDuration()?'가사의 흐름에 맞춰 구성 (시간 직접 지정 안 함)':Number(duration.value)+'초';
    const request=`감성적이고 창의적인 작사가가 되어서 다음 조건에 맞는 새로운 노래 가사를 작성해 줘.

${title?'* 제목: '+title+'\n':''}* 음악/노래 주제/설명: ${description}
* 가사 언어: ${language==='기타 언어'?'원하는 언어로 작성하되, 먼저 어떤 언어인지 물어봐 주세요':language}
* 곡 길이: ${seconds}
* 요청사항.1: 구간 표시는 [Verse], [Chorus] 같이 대괄호 안에 영어로 표기할 것
* 요청사항.3: [Intro], [Outro], [Instrumental]의 연주 설명은 가사 안에 영어로, 괄호를 사용해 표기할 것. 예: (Soft piano instrumental). 실제 노랫말은 요청한 가사 언어로 작성할 것\n* 요청사항.2: 설명이나 코드 블록 없이 가사만 출력하고 요청자가 제목을 입력하지 않았을 경우 적절한 제목 만들기
* 주의사항: 저작권 문제가 될 수 있는 기존 노래의 가사를 인용하지 말고 완전히 새로 작성할 것`;
    try{
        await navigator.clipboard.writeText(request);
        $('lyric-request-fallback').hidden=true;
        $('lyric-tools-status').textContent='요청문을 복사했습니다. 위 AI 도구를 열어 붙여넣으세요.';
    }catch{
        const field=$('lyric-request-fallback');field.value=request;field.hidden=false;field.focus();field.select();
        $('lyric-tools-status').textContent='아래 요청문을 선택해 복사한 뒤 AI 도구에 붙여넣으세요.';
    }
};

// Native dialogs trap keyboard focus and return it to the opening control.
function bindModal(dialogId,openerId,closeIds,onOpen=()=>{}){
    const dialog=$(dialogId),opener=$(openerId);
    opener.onclick=()=>{onOpen();dialog.showModal();};
    closeIds.forEach(id=>$(id).onclick=()=>dialog.close());
    dialog.addEventListener('click',event=>{
        const box=dialog.getBoundingClientRect();
        if(event.target===dialog&&(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom))dialog.close();
    });
    dialog.addEventListener('close',()=>opener.focus({preventScroll:true}));
}
bindModal('sponsor-dialog','open-sponsor',['close-sponsor'],()=>{$('sponsor-status').textContent='';});
bindModal('privacy-dialog','open-privacy',['close-privacy','confirm-privacy']);
bindModal('license-dialog','open-license',['close-license']);
$('paypal-sponsor').onclick=async()=>{
    const button=$('paypal-sponsor'),status=$('sponsor-status');
    button.disabled=true;status.textContent='기본 웹브라우저를 열고 있습니다…';
    try{await api('/api/sponsor/paypal',{});status.textContent='기본 웹브라우저에서 PayPal 후원 페이지를 열었습니다.';}
    catch(error){status.textContent=error.message;}
    finally{button.disabled=false;}
};
