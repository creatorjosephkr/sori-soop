let cancelling=false;
let qualityInstallRequest=false,qualityInstallError='';
let sa3InstallRequest=false,sa3InstallError='';
let state, mode='bgm', bgmModelChoice='small-music', dirty=false;
let jobHistory=[];
const durationOverrides={};
let durationDraft=false;
function songAutoDuration(){return mode==='song'&&$('song-duration-mode').value==='auto';}
function renderDurationInput(){
    const input=$('seconds-number'),slider=$('seconds');
    if(input.min!==slider.min||input.max!==slider.max||input.dataset.mode!==mode)durationDraft=false;
    input.min=slider.min;input.max=slider.max;input.dataset.mode=mode;
    if(!durationDraft)input.value=slider.value;
    const valid=input.value!==''&&input.validity.valid;
    input.setAttribute('aria-invalid',String(!valid));
    $('duration-error').textContent=valid?'':`길이를 ${input.min}~${input.max}초 사이의 정수로 입력하세요.`;
}

function updatePromptCount(){const count=Array.from($('prompt').value).length;setText('prompt-character-count',count.toLocaleString('ko-KR')+' / 2,000자 · 공백·줄바꿈 포함');$('prompt-character-count').classList.toggle('over-limit',count>2000);}
function setText(id,text){if($(id)&&$(id).textContent!==text)$(id).textContent=text;}
const $=id=>document.getElementById(id);
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,body){const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw Error(data.error||'요청에 실패했습니다.');return data;}
function recommendation(){const s=state.system;const hasNvidia=Boolean(s.gpu&&s.gpu.some(g=>g.vramGB>=5.5));const low=(s.ramGB||0)<12||(s.availableGB!==null&&s.availableGB<4);const recBackend=s.appleSilicon?'apple':((hasNvidia&&mode==='song')?'cuda':'cpu');return {model:mode==='song'?'ace-step':(mode==='sfx'?'small-sfx':bgmModelChoice),backend:recBackend,seconds:mode==='sfx'?5:((low||mode==='song')?30:60)};}
function applyRecommendation(){const r=recommendation();for(const k of ['model','backend'])$(k).value=r[k];const m=state.models[r.model];$('seconds').min=m.minSeconds??10;$('seconds').max=m.maxSeconds;$('seconds').value=durationOverrides[mode]??r.seconds;}
function render(){if(!state)return;const auto=$('policy').value==='auto';$('backend').disabled=auto;for(const opt of $('backend').options){if(opt.value==='apple')opt.hidden=!state.system.appleSilicon;else if(opt.value==='cuda')opt.hidden=!state.system.gpu?.some(g=>g.vramGB>=5.5);}$('model').disabled=auto&&mode!=='bgm';for(const opt of $('model').options){const match=state.models[opt.value]?.mode===mode;opt.hidden=auto&&!match;opt.disabled=auto&&!match;}$('seconds').disabled=false;$('bgm').classList.toggle('selected',mode==='bgm');$('song').classList.toggle('selected',mode==='song');$('sfx').classList.toggle('selected',mode==='sfx');$('lyrics-wrap').hidden=mode!=='song';if($('song-lyric-tools-wrap'))$('song-lyric-tools-wrap').hidden=mode!=='song';window.MusicPresets?.setMode(mode);const m=state.models[$('model').value]||state.models['small-music'];const minSec=m.minSeconds??10;$('seconds').min=minSec;$('seconds').max=m.maxSeconds;if(+$('seconds').value<minSec)$('seconds').value=minSec;if(+$('seconds').value>m.maxSeconds)$('seconds').value=m.maxSeconds;renderDurationInput();if($('min'))$('min').textContent=minSec+'초';$('max').textContent='모델 최대 '+m.maxSeconds+'초';const r=recommendation();$('basis').textContent=r.basis||'사양 기반 · 실측 전';const warnings=[];if(!songAutoDuration()&&+$('seconds').value>r.seconds)warnings.push('초기 권장 길이를 초과했습니다. 메모리 부족이나 처리 지연 가능성을 실기기에서 확인해야 합니다.');if(mode==='song'&&!songAutoDuration())warnings.push('가사를 직접 입력하고 짧은 노래부터 시작하세요. '+(state.system.ramGB<12?'8GB급 환경에서는 안정적인 실행을 보장할 수 없습니다.':'30~60초부터 실제 실행 검증이 필요합니다.'));if(mode==='song'&&!songAutoDuration()&&$('lyrics').value.replace(/\[[^\]]*\]/g,'').replace(/\s/g,'').length>+$('seconds').value*4)warnings.push('현재 길이에 비해 가사가 많습니다. 일부 가사가 생략될 수 있으니 자동 길이를 선택하거나 길이를 늘려 주세요.');if(mode==='song'&&!m.vocals)warnings.push('선택한 모델은 가사 기반 노래를 지원하지 않습니다. ACE-Step을 선택하세요.');if(mode!=='song'&&m.mode!==mode)warnings.push(mode==='sfx'?'효과음 만들기에는 Small-SFX 모델을 선택하세요.':'배경음악 만들기에는 Small-Music 또는 Medium 모델을 선택하세요.');if($('backend').value==='apple'&&!state.system.appleSilicon)warnings.push('Apple Silicon이 감지되지 않았습니다. CPU 실행 방식을 선택하세요.');if($('backend').value==='cuda'&&!state.system.gpu?.some(g=>g.vramGB>=5.5))warnings.push('NVIDIA GPU 가속(CUDA)에 필요한 외장 그래픽이 감지되지 않았습니다. CPU를 선택하세요.');if(state.system.availableGB!==null&&state.system.availableGB<3)warnings.push('가용 메모리가 적습니다. 다른 앱을 종료하고 다시 진단하세요.');const warningHTML=warnings.map(w=>`<div class="warning">${escapeHTML(w)}</div>`).join('');if($('warnings').innerHTML!==warningHTML)$('warnings').innerHTML=warningHTML;$('save').disabled=false;}
async function refresh(initial=false){try{$('refresh').disabled=true;const next=await api('/api/status');state=next;if(initial){mode=['bgm','song','sfx'].includes(next.settings.mode)?next.settings.mode:'bgm';if(next.settings.model==='medium')bgmModelChoice='medium';$('song-quality').value=next.settings.songQuality==='quality'?'quality':'light';$('song-duration-mode').value=next.settings.durationMode==='manual'?'manual':'auto';$('peak-db').value=next.settings.peakDb??-8;if(Number.isInteger(next.settings.seconds))durationOverrides[mode]=next.settings.seconds;if(next.settings.exaoneApiKey)$('exaone-api-key').value=next.settings.exaoneApiKey;if(next.settings.exaoneTimeout!==undefined&&$('lyric-gen-timeout'))$('lyric-gen-timeout').value=String(next.settings.exaoneTimeout);$('policy').value=next.settings.policy;if(next.settings.policy==='auto')applyRecommendation();else for(const k of ['model','backend','seconds']){if(k==='seconds'){const m=next.models[$('model').value]||next.models['small-music'];$('seconds').min=m.minSeconds??10;$('seconds').max=m.maxSeconds;}if(next.settings[k]!==undefined)$(k).value=next.settings[k];}}else if($('policy').value==='auto')applyRecommendation();const s=state.system;const rows=[['시스템',s.os==='Darwin'?'macOS':s.os],['프로세서',s.chip],['전체 메모리',s.ramGB===null?'확인 불가':s.ramGB+' GB'],['현재 가용량 ≈',s.availableGB===null?'확인 불가':s.availableGB+' GB'],['그래픽',s.appleSilicon?'Apple 통합 그래픽':s.gpu.map(g=>g.name+' / '+g.vramGB+' GB').join(', ')||'NVIDIA 미감지 · 기타 GPU 미확인'],['여유 저장 공간',s.diskFreeGB+' GB']];$('system').innerHTML=rows.map(([k,v])=>`<div class="metric"><span>${escapeHTML(k)}</span><b>${escapeHTML(v).replace(/(\d+(?:\.\d+)?) GB/g,'$1&nbsp;GB')}</b></div>`).join('');render();if(!initial)$('message').textContent='진단을 갱신했습니다. 직접 설정과 고정값은 유지됩니다.';}catch(e){$('message').textContent=e.message;}finally{$('refresh').disabled=false;}}
for(const id of ['bgm','song','sfx'])$(id).onclick=()=>{if(!state)return;mode=id;dirty=true;sa3InstallError='';if($('policy').value!=='manual')applyRecommendation();render();};
$('policy').onchange=()=>{if(!state)return;if($('policy').value!=='manual')applyRecommendation();dirty=true;render();};
$('song-quality').onchange=()=>{dirty=true;qualityInstallError='';render();};
$('prepare-song-quality').onclick=async()=>{
    if(window.StudioSetup?.active&&window.StudioSetup.status?.component==='song-quality'){window.StudioSetup.open();return;}
    if(qualityInstallRequest)return;
    qualityInstallRequest=true;qualityInstallError='';render();
    try{await window.StudioSetup.prepareQuality();}
    catch(e){qualityInstallError=e.message;$('message').textContent=e.message;}
    finally{qualityInstallRequest=false;render();}
};
$('prepare-sa3-model').onclick=async()=>{
    const comp=$('model').value==='medium'?'bgm-medium':'sfx';
    if(window.StudioSetup?.active&&window.StudioSetup.status?.component===comp){window.StudioSetup.open();return;}
    if(sa3InstallRequest)return;
    sa3InstallRequest=true;sa3InstallError='';render();
    try{await window.StudioSetup.prepareComponent(comp);}
    catch(e){sa3InstallError=e.message;$('message').textContent=e.message;}
    finally{sa3InstallRequest=false;render();}
};
$('song-duration-mode').onchange=()=>{dirty=true;render();};
$('model').oninput=()=>{if(mode==='bgm'&&['small-music','medium'].includes($('model').value))bgmModelChoice=$('model').value;sa3InstallError='';dirty=true;render();};
$('backend').oninput=()=>{dirty=true;render();};
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

function selectedSettings(){const duration=$('seconds-number');if(!songAutoDuration()&&(duration.value===''||!duration.checkValidity())){duration.focus();duration.reportValidity();throw Error(`음악 길이를 ${duration.min}~${duration.max}초 사이의 정수로 입력하세요.`);}if($('peak-db').value.trim()===''||!$('peak-db').checkValidity())throw Error('최대 게인은 -24~0dB 범위로 설정하세요.');return {peakDb:Number($('peak-db').value),policy:$('policy').value,mode,model:$('model').value,backend:$('backend').value,seconds:songAutoDuration()?null:+$('seconds').value,...(mode==='song'?{durationMode:$('song-duration-mode').value,songQuality:$('song-quality').value}:{})};}
const generateButton=document.querySelector('.generate');
let submitting=false, activeJob=false;
$('lyrics').addEventListener('input',()=>render());
$('prompt').addEventListener('input',updatePromptCount);
updatePromptCount();
$('peak-db').oninput=()=>{dirty=true;};
function renderSongQuality(){
    const quality=$('song-quality').value==='quality',qualityReady=state.songPlanners?.quality===true;
    const setup=window.StudioSetup,installing=!!setup?.active&&setup.status?.component==='song-quality';
    const busy=installing||qualityInstallRequest,baseReady=!!state.songEngines?.[$('backend').value];
    const error=qualityInstallError||(!qualityReady&&setup?.status?.component==='song-quality'&&setup.status.state==='failed'?setup.status.error:'');
    const notice=$('quality-install-notice'),button=$('prepare-song-quality');
    notice.hidden=mode!=='song'||!quality;
    $('song-quality').setAttribute('aria-describedby',quality?'quality-install-title quality-install-message song-quality-help':'song-quality-help');
    notice.classList.toggle('is-ready',qualityReady);notice.classList.toggle('is-installing',busy&&!qualityReady);notice.classList.toggle('is-error',!!error&&!qualityReady);
    setText('quality-install-title',qualityReady?'1.7B 품질 모델이 설치되어 있습니다.':busy?'1.7B 품질 모델을 설치하고 있습니다.':error?'품질 모델 설치를 완료하지 못했습니다.':'1.7B 품질 모델이 아직 설치되어 있지 않습니다.');
    const blocked=!baseReady?'먼저 왼쪽 사이드바에서 기본 실행 준비를 완료해 주세요.':activeJob?'현재 음악 생성이 끝나면 설치할 수 있습니다.':setup?.active&&!installing?'다른 모델 준비가 끝나면 설치할 수 있습니다.':'';
    setText('quality-install-message',qualityReady?(setup?.active?'모델 설치를 마쳤습니다. 진행 중인 준비가 끝나면 사용할 수 있습니다.':'설치가 완료되어 노래 생성에 사용할 수 있습니다.'):busy?'다운로드와 설치가 진행 중입니다. 진행 상황 창에서 처리 내용을 확인할 수 있습니다.':(error?error+' ':'')+'처음 한 번 약 3.7GB를 다운로드하면 이 컴퓨터에서 사용할 수 있습니다. 아래 설치 버튼을 눌러 주세요.'+(blocked?' '+blocked:''));
    button.hidden=mode!=='song'||!quality||qualityReady;
    button.disabled=qualityInstallRequest||(!installing&&(activeJob||submitting||!!setup?.active||!baseReady));
    setText('prepare-song-quality',installing?'설치 진행 상황 보기':qualityInstallRequest?'설치를 시작하고 있습니다…':error?'1.7B 품질 모델 설치 다시 시도':'1.7B 품질 모델 설치 · 약 3.7GB');
    setText('song-quality-help',quality?'RAM 16GB 이상을 권장합니다. CPU에서는 느릴 수 있으며 Windows의 품질 모델 성능은 추가 검증이 필요합니다. 가사·발음의 완벽한 일치는 보장하지 않습니다.':'적은 메모리와 빠른 준비를 위한 모델입니다. 긴 노래에서는 가사 누락·오발음이 생길 수 있습니다.');
    return {quality,qualityReady};
}
function renderSa3Model(){
    const selected=$('model').value;
    const isExtra=mode!=='song'&&(selected==='medium'||selected==='small-sfx');
    const comp=selected==='medium'?'bgm-medium':'sfx';
    const label=selected==='medium'?'Stable Audio 3 Medium 고품질 배경음악':'Stable Audio 3 Small-SFX 효과음';
    const sizeText=selected==='medium'?($('backend').value==='apple'?'약 5.5GB':'약 1.8GB'):($('backend').value==='apple'?'약 1.1GB':'약 0.6GB');
    const ready=state.sa3Models?.[$('backend').value]?.[selected]===true;
    const setup=window.StudioSetup,installing=!!setup?.active&&setup.status?.component===comp;
    const busy=installing||sa3InstallRequest,baseReady=!!state.engines?.[$('backend').value];
    const error=sa3InstallError||(!ready&&setup?.status?.component===comp&&setup.status.state==='failed'?setup.status.error:'');
    const notice=$('sa3-install-notice'),button=$('prepare-sa3-model');
    notice.hidden=!isExtra;
    notice.classList.toggle('is-ready',ready);notice.classList.toggle('is-installing',busy&&!ready);notice.classList.toggle('is-error',!!error&&!ready);
    setText('sa3-install-title',ready?`${label} 모델이 설치되어 있습니다.`:busy?`${label} 모델을 설치하고 있습니다.`:error?`${label} 모델 설치를 완료하지 못했습니다.`:`${label} 모델이 아직 설치되어 있지 않습니다.`);
    const blocked=!baseReady?'먼저 왼쪽 사이드바에서 기본 실행 준비를 완료해 주세요.':activeJob?'현재 작업이 끝나면 설치할 수 있습니다.':setup?.active&&!installing?'다른 모델 준비가 끝나면 설치할 수 있습니다.':'';
    setText('sa3-install-message',ready?(setup?.active?'모델 설치를 마쳤습니다. 진행 중인 준비가 끝나면 사용할 수 있습니다.':(selected==='medium'?'설치가 완료되어 최대 380초 고품질 배경음악 생성에 사용할 수 있습니다.':'설치가 완료되어 효과음 생성에 사용할 수 있습니다.')):busy?'다운로드와 설치가 진행 중입니다. 진행 상황 창에서 처리 내용을 확인할 수 있습니다.':(error?error+' ':'')+`처음 한 번 ${sizeText}를 다운로드하면 이 컴퓨터에서 사용할 수 있습니다. 아래 설치 버튼을 눌러 주세요.`+(blocked?' '+blocked:''));
    button.hidden=!isExtra||ready;
    button.disabled=sa3InstallRequest||(!installing&&(activeJob||submitting||!!setup?.active||!baseReady));
    setText('prepare-sa3-model',installing?'설치 진행 상황 보기':sa3InstallRequest?'설치를 시작하고 있습니다…':error?`${label} 모델 설치 다시 시도`:`${label} 모델 설치 · ${sizeText}`);
    return {ready};
}
const originalRender=render;
render=function(){originalRender();updatePromptCount();generateButton.classList.toggle('is-generating',submitting||activeJob);$('song-duration-mode-wrap').hidden=mode!=='song';$('manual-duration-controls').hidden=songAutoDuration();$('auto-duration-help').hidden=!songAutoDuration();$('seconds').disabled=songAutoDuration();$('seconds-number').disabled=songAutoDuration();$('generation-status').classList.toggle('is-generating',submitting||activeJob);$('cancel-generation').hidden=!activeJob;$('cancel-generation').disabled=cancelling;$('cancel-generation').innerHTML=window.StudioIcons('stop')+' <span>'+(cancelling?'중단 요청 중…':'생성 중단')+'</span>';$('song-quality-wrap').hidden=mode!=='song';if(!state)return;const {quality,qualityReady}=renderSongQuality();const {ready:sa3ExtraReady}=renderSa3Model();setText('prompt-limit-help',mode==='song'?'음악 설명은 최대 2,000자까지 입력할 수 있습니다. 번역 후 음악 설명·내부 지시문을 포함해 엔진 한도인 256토큰을 검사합니다. 초과하면 줄일 수 있도록 안내하며 자동으로 자르지 않습니다.':'설명은 최대 2,000자까지 입력할 수 있습니다.');setText('prompt-language-help',state.translationReady?'한글로 입력한 설명은 내 컴퓨터에서 영어로 자동 변환해 생성에 사용합니다. 제목과 가사는 원문을 유지합니다.':'한글 자동 번역 모델이 준비되지 않았습니다. 영어 설명이나 프리셋을 사용해 주세요.');const selectedModel=$('model').value;const supported=(mode==='bgm'&&((selectedModel==='small-music'&&state.engines[$('backend').value])||(selectedModel==='medium'&&sa3ExtraReady)))||(mode==='sfx'&&selectedModel==='small-sfx'&&sa3ExtraReady)||(mode==='song'&&selectedModel==='ace-step'&&state.songEngines?.[$('backend').value]&&(!quality||qualityReady));generateButton.disabled=!supported||submitting||activeJob||window.StudioSetup?.active;const modeLabel=mode==='song'?'노래 만들기':(mode==='sfx'?'효과음 만들기':'배경음악 만들기');const buttonLabel=(submitting||activeJob)?'생성 중…':modeLabel;const buttonHTML=window.StudioIcons((submitting||activeJob)||mode==='song'?'music':'sparkles')+' <span>'+buttonLabel+'</span>';if(generateButton.innerHTML!==buttonHTML)generateButton.innerHTML=buttonHTML;$('new-track').setAttribute('aria-label',mode==='song'?'노래 새로 만들기':(mode==='sfx'?'효과음 새로 만들기':'배경음악 새로 만들기'));document.querySelector('.composer>.footnote').textContent=mode==='song'?'ACE-Step · 입력한 가사로 보컬과 반주를 함께 생성합니다. 첫 생성은 모델 준비 시간이 포함됩니다.':mode==='sfx'?'Stable Audio 3 Small-SFX · 자연음, 폴리, UI, SF 등 다양한 효과음을 생성합니다.':selectedModel==='medium'?'Stable Audio 3 Medium · 고품질 배경음악을 최대 380초까지 생성합니다.':(state.translationReady?'Small-Music 배경음악 생성 · 한글·영어 설명과 프리셋을 사용할 수 있습니다.':'Small-Music 배경음악 생성 · 영어 설명 또는 프리셋을 사용해 주세요.');document.querySelector('label[for="prompt"]').textContent=mode==='song'?'곡의 장르와 분위기를 설명해 주세요':(mode==='sfx'?'만들고 싶은 효과음을 설명해 주세요':'떠오르는 음악을 설명해 주세요');$('prompt').placeholder=mode==='sfx'?'나무 바닥 위를 천천히 걷는 발자국 소리와 멀리서 들리는 빗소리.':'햇살이 들어오는 카페, 따뜻한 피아노와 부드러운 드럼. 일상의 기록에 어울리는 차분한 음악.';$('track-title').placeholder=mode==='sfx'?'예: 밤비 내리는 창가 소리':'예: 햇살이 머무는 아침';};
const DEFAULT_NEGATIVE_PROMPT='low quality, muddy mix, clipping, distortion, harsh high frequencies, out of tune, arrhythmia, sudden silence, background noise, hiss, hum, muffled audio, robotic voice, slurred pronunciation, gibberish, abrupt cut';
$('reset-negative-prompt').onclick=()=>{$('negative-prompt').value=DEFAULT_NEGATIVE_PROMPT;};
generateButton.onclick=async()=>{submitting=true;render();$('results-notice').textContent='';$('generation-status').textContent='생성 요청을 보내고 있습니다…';try{const created=await api('/api/generate',{settings:selectedSettings(),title:$('track-title').value,prompt:$('prompt').value,negativePrompt:$('negative-prompt').value,lyrics:$('lyrics').value,language:$('language').value});resultPages[created.settings.mode]=1;selectResultTab(created.settings.mode);$('message').textContent='';$('results-notice').textContent='생성을 시작했습니다. 다른 작업은 완료 후 시작할 수 있습니다.';await jobs();$('results').scrollIntoView({block:'start',behavior:'instant'});}catch(e){$('message').textContent=e.message;$('generation-status').textContent=e.message;}finally{submitting=false;render();}};
$('cancel-generation').onclick=async()=>{if(cancelling)return;cancelling=true;render();try{await api('/api/cancel',{});$('message').textContent='생성 중단을 요청했습니다.';await jobs();}catch(e){$('message').textContent=e.message;}finally{cancelling=false;render();}};
const statusLabels={queued:'대기 중',running:'생성 중',completed:'완료',cancelled:'취소됨',failed:'실패',interrupted:'중단됨'};
let jobsSignature='';
const RESULT_MODES=['bgm','song','sfx'];
let resultMode=RESULT_MODES.includes(localStorage.getItem('music-result-tab'))?localStorage.getItem('music-result-tab'):'bgm';
function getPageSize(mode){return mode==='song'?20:10;}
const resultPages={bgm:1,song:1,sfx:1};
const selectedJobIds=new Set();
let paginationSignature='';
function selectResultTab(value){
    if(!RESULT_MODES.includes(value))value='bgm';
    resultMode=value;localStorage.setItem('music-result-tab',value);
    selectedJobIds.clear();
    for(const key of RESULT_MODES){
        const tab=$('results-'+key);
        tab.classList.toggle('selected',key===value);
        tab.setAttribute('aria-selected',String(key===value));
        tab.tabIndex=key===value?0:-1;
    }
    $('jobs').setAttribute('aria-labelledby','results-'+value);
    syncBatchSelectionUI();
}
for(const key of RESULT_MODES){
    $('results-'+key).onclick=()=>{selectResultTab(key);jobs();};
    $('results-'+key).onkeydown=event=>{
        if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
        event.preventDefault();
        const idx=RESULT_MODES.indexOf(resultMode);
        const next=event.key==='Home'?RESULT_MODES[0]:event.key==='End'?RESULT_MODES[RESULT_MODES.length-1]:RESULT_MODES[(idx+(event.key==='ArrowRight'?1:RESULT_MODES.length-1))%RESULT_MODES.length];
        selectResultTab(next);$('results-'+next).focus();jobs();
    };
}
selectResultTab(resultMode);
const resultSignatures=new Map();
const expandedResults=new Set();
function getCurrentPageJobs(){
    const currentModeJobs=jobHistory.filter(j=>(j.settings.mode||'bgm')===resultMode);
    const pageSize=getPageSize(resultMode);
    const page=resultPages[resultMode]||1;
    return currentModeJobs.slice((page-1)*pageSize,page*pageSize);
}
function syncBatchSelectionUI(){
    const existingIds=new Set(jobHistory.map(j=>j.id));
    for(const id of selectedJobIds){if(!existingIds.has(id))selectedJobIds.delete(id);}
    const count=selectedJobIds.size;
    const countSpan=$('selected-count');
    if(countSpan)countSpan.textContent=count;
    const deleteBtn=$('delete-selected-results');
    if(deleteBtn){
        deleteBtn.disabled=count===0;
        deleteBtn.textContent=`선택 삭제 (${count})`;
    }
    const pageJobs=getCurrentPageJobs().filter(j=>!['queued','running'].includes(j.status));
    const pageSelected=pageJobs.filter(j=>selectedJobIds.has(j.id));
    const selectAllCheckbox=$('select-all-results');
    if(selectAllCheckbox){
        if(pageJobs.length>0&&pageSelected.length===pageJobs.length){
            selectAllCheckbox.checked=true;
            selectAllCheckbox.indeterminate=false;
        }else if(pageSelected.length>0){
            selectAllCheckbox.checked=false;
            selectAllCheckbox.indeterminate=true;
        }else{
            selectAllCheckbox.checked=false;
            selectAllCheckbox.indeterminate=false;
        }
    }
    for(const cb of document.querySelectorAll('.result-item-checkbox')){
        cb.checked=selectedJobIds.has(cb.dataset.selectId);
    }
}
function renderResultPage(allItems){
    const pageSize=getPageSize(resultMode);
    const total=allItems.length;
    const pages=Math.max(1,Math.ceil(total/pageSize));
    const page=Math.max(1,Math.min(resultPages[resultMode],pages));
    resultPages[resultMode]=page;
    const items=allItems.slice((page-1)*pageSize,page*pageSize);
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
    syncBatchSelectionUI();
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
function formatDuration(value){const s=Math.max(0,Math.floor(Number(value)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')} (${s}초)`;}
function durationText(job){if(Number.isFinite(job.durationSeconds))return musicTime(job.durationSeconds);return job.settings.durationMode==='auto'?'자동 · 가사 기준':musicTime(job.settings.seconds);}
function resultMarkup(job){
    const settings=job.settings;
    const pending=['queued','running'].includes(job.status);
    const title=job.title?.trim()||(job.title===undefined?job.prompt:'')||(settings.mode==='song'?'보컬 노래':(settings.mode==='sfx'?'효과음':'배경음악'));
    const filename=(job.title?.trim()||('music-'+job.id)).replace(/[\\/:*?"<>|\x00-\x1f]/g,'-').replace(/[. ]+$/,'').slice(0,80)||('music-'+job.id);
    const date=new Date(job.createdAt*1000).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const language=({ko:'한국어',en:'영어',ja:'일본어',zh:'중국어',unknown:'기타 언어'})[job.language]||job.language;
    const info=[['모델',state?.models[settings.model]?.name||settings.model],['실행 방식',settings.backend==='apple'?'Apple Silicon':(settings.backend==='cuda'?'NVIDIA CUDA 가속':'CPU')],['음악 길이',durationText(job)]];
    if(job.composition?.metadata?.bpm)info.push(['곡 구성 템포',job.composition.metadata.bpm+' BPM']);
    if(job.composition?.plannerModel)info.push(['곡 구성 모델',job.composition.plannerModel.includes('1.7B')?'품질 우선 · 1.7B':'가벼운 모델 · 0.6B']);
    if(language)info.push(['보컬 언어',language]);
    if(job.negativePrompt)info.push(['네거티브 프롬프트',job.negativePrompt]);
    if(settings.peakDb!==undefined)info.push(['최대 게인',settings.peakDb+'dB']);
    if(Number.isFinite(job.outputPeakDb))info.push(['실제 피크',job.outputPeakDb.toFixed(1)+'dB']);
    if(Number.isFinite(job.elapsedSeconds))info.push(['처리 시간',formatDuration(job.elapsedSeconds)]);
    if(job.processPeakGB)info.push(['프로세스 최고 메모리',job.processPeakGB+'GB']);
    if(job.enginePeakGB)info.push(['엔진 최고 메모리',job.enginePeakGB+'GB']);
    return `<details id="result-${escapeHTML(job.id)}" data-job-id="${escapeHTML(job.id)}" class="notice result-item result-disclosure ${escapeHTML(job.status)}">
      <summary class="result-summary"><label class="result-checkbox-label" onclick="event.stopPropagation()"><input type="checkbox" class="result-item-checkbox" data-select-id="${escapeHTML(job.id)}" aria-label="선택" ${pending?'disabled':''} ${selectedJobIds.has(job.id)?'checked':''}></label>${pending?`<span class="result-loading" role="status" aria-label="${job.status==='queued'?'생성 대기 중':'음악 생성 중'}">${window.StudioIcons('spinner')}</span>`:`<button type="button" class="result-play" data-play="${escapeHTML(job.id)}" aria-label="${job.audioUrl?'재생':'생성 완료 후 재생 가능'}" title="${job.audioUrl?'펼쳐서 재생':'생성 완료 후 재생 가능'}" aria-pressed="false" ${job.audioUrl?'':'disabled'}><span aria-hidden="true">${window.StudioIcons('play')}</span></button>`}<span class="result-summary-main"><span class="result-summary-title">${escapeHTML(title)}</span><span class="result-summary-meta"><span class="result-state ${escapeHTML(job.status)}">${escapeHTML(statusLabels[job.status]||job.status)}</span><span>${escapeHTML(durationText(job))}</span><span>${escapeHTML(date)}</span></span></span><span class="result-chevron" aria-hidden="true">${window.StudioIcons('chevron')}</span></summary>
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
        message.textContent=resultMode==='song'?'가사를 입력하고 노래를 생성하면 여기에 표시됩니다.':(resultMode==='sfx'?'설명을 입력하고 효과음을 생성하면 여기에 표시됩니다.':'배경음악을 생성하면 여기에 표시됩니다.');
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
async function jobs(){try{const data=await api('/api/jobs');jobHistory=data.jobs;activeJob=data.jobs.some(j=>['queued','running'].includes(j.status));const visibleJobs=data.jobs.filter(j=>(j.settings.mode||'bgm')===resultMode);for(const key of RESULT_MODES)$('count-'+key).textContent=data.jobs.filter(j=>(j.settings.mode||'bgm')===key).length;const latest=visibleJobs[0];const running=data.jobs.find(j=>['queued','running'].includes(j.status));const kind=resultMode==='song'?'보컬 노래':(resultMode==='sfx'?'효과음':'배경음악');const runningKind=running?.settings.mode==='song'?'보컬 노래':(running?.settings.mode==='sfx'?'효과음':'배경음악');$('generation-status').textContent=running?`${running.phase||(runningKind+' 생성 중')} · ${formatDuration(Date.now()/1000-running.createdAt)} 경과`:latest?`${kind} 최근 작업: ${statusLabels[latest.status]||latest.status} · 총 ${visibleJobs.length}개`:`아직 생성한 ${kind} 결과가 없습니다.`;render();renderResultPage(visibleJobs);}catch(e){$('message').textContent=e.message;}}
setInterval(jobs,2000);jobs();
$('new-track').onclick=()=>{resetDraftInputs();$('lyric-tools-status').textContent='';$('lyric-request-fallback').value='';$('lyric-request-fallback').hidden=true;$('message').textContent='새 '+(mode==='song'?'노래':(mode==='sfx'?'효과음':'배경음악'))+'를 만들 준비가 되었습니다.';updatePromptCount();$('track-title').focus();};

const benchmarkButton=document.createElement('button');benchmarkButton.className='save';benchmarkButton.textContent='성능 측정 · 20초 배경음악';
const sampleSongButton=document.createElement('button');sampleSongButton.className='save';sampleSongButton.textContent='샘플 노래 만들기';
document.querySelector('.sidebar-tip').append(benchmarkButton,sampleSongButton);
const SAMPLE_SONG_PROMPT='Korean city pop, retro synth bass, electric piano, funky rhythm guitar, dreamy female vocal, clear vocal diction, nostalgic night vibe, 108 BPM';
const SAMPLE_SONG_LYRICS='[ko]\n[Intro]\n\n[Verse 1]\n차갑게 식어가는, 커피 한 잔\n창가에 비친, 네온사인 불빛\n오늘 하루도, 참 길어써-\n조용히 한숨을, 내쉬어 보네\n\n[Pre-Chorus]\n복자판 생각은, 이제 지우고\n가벼운 걸음으로, 나아가 볼까\n\n[Chorus]\n빈나는 별비치, 내게 쏟아져-\n가치 걸어가는, 이 밤의 거리\n조아하는 노래를, 흥얼거리며\n내일은 더 따스할, 꿈을 꾸네-';
benchmarkButton.onclick=async()=>{if(!state)return;submitting=true;render();benchmarkButton.disabled=true;$('results-notice').textContent='';$('generation-status').textContent='성능 측정을 시작하고 있습니다…';try{const peakDb=($('peak-db').value.trim()!==''&&$('peak-db').checkValidity())?Number($('peak-db').value):-8;await api('/api/generate',{settings:{policy:'manual',mode:'bgm',model:'small-music',backend:$('backend').value,seconds:20,peakDb},prompt:'Warm instrumental piano music with soft drums, no vocals.',negativePrompt:$('negative-prompt').value});resultPages.bgm=1;selectResultTab('bgm');$('results-notice').textContent='20초 음악을 생성해 처리 시간을 측정합니다. 첫 실행은 초기화 시간이 포함됩니다.';await jobs();$('results').scrollIntoView({block:'start',behavior:'instant'});}catch(e){$('message').textContent=e.message;}finally{submitting=false;benchmarkButton.disabled=false;render();}};
sampleSongButton.onclick=async()=>{if(!state)return;mode='song';if($('policy').value!=='manual')applyRecommendation();$('prompt').value=SAMPLE_SONG_PROMPT;$('lyrics').value=SAMPLE_SONG_LYRICS;$('language').value='ko';localStorage.setItem('music-language','ko');$('song-duration-mode').value='auto';submitting=true;render();sampleSongButton.disabled=true;$('results-notice').textContent='';$('generation-status').textContent='샘플 노래 생성을 시작하고 있습니다…';try{const peakDb=($('peak-db').value.trim()!==''&&$('peak-db').checkValidity())?Number($('peak-db').value):-8;const songQuality=($('song-quality').value==='quality'&&state.songPlanners?.quality)?'quality':'light';await api('/api/generate',{settings:{policy:'manual',mode:'song',model:'ace-step',backend:$('backend').value,seconds:null,durationMode:'auto',songQuality,peakDb},title:'샘플 노래 · 시티팝',prompt:SAMPLE_SONG_PROMPT,negativePrompt:$('negative-prompt').value,lyrics:SAMPLE_SONG_LYRICS,language:'ko'});resultPages.song=1;selectResultTab('song');$('message').textContent='';$('results-notice').textContent='샘플 노래 생성을 시작했습니다. 다른 작업은 완료 후 시작할 수 있습니다.';await jobs();$('results').scrollIntoView({block:'start',behavior:'instant'});}catch(e){$('message').textContent=e.message;$('generation-status').textContent=e.message;}finally{submitting=false;sampleSongButton.disabled=false;render();}};
function resetDraftInputs(){
    $('track-title').value='';$('prompt').value='';$('negative-prompt').value=DEFAULT_NEGATIVE_PROMPT;$('lyrics').value='';window.MusicPresets?.reset();updatePromptCount();
    localStorage.removeItem('music-prompt');localStorage.removeItem('music-lyrics');
}
resetDraftInputs();
// Clear browser-restored form values after a fresh load as well.
window.addEventListener('pageshow',event=>{if(!event.persisted)resetDraftInputs();});

$('jobs').addEventListener('change',event=>{
    const cb=event.target.closest('.result-item-checkbox');
    if(!cb)return;
    const id=cb.dataset.selectId;
    if(cb.checked)selectedJobIds.add(id);
    else selectedJobIds.delete(id);
    syncBatchSelectionUI();
});

if($('select-all-results'))$('select-all-results').onchange=()=>{
    const checked=$('select-all-results').checked;
    const pageJobs=getCurrentPageJobs().filter(j=>!['queued','running'].includes(j.status));
    for(const job of pageJobs){
        if(checked)selectedJobIds.add(job.id);
        else selectedJobIds.delete(job.id);
    }
    syncBatchSelectionUI();
};

if($('delete-selected-results'))$('delete-selected-results').onclick=async()=>{
    const toDelete=Array.from(selectedJobIds);
    if(!toDelete.length)return;
    if(!confirm(`선택한 ${toDelete.length}개의 생성 결과를 삭제하시겠습니까?\n삭제된 파일은 로컬 휴지통에 보관됩니다.`))return;
    const btn=$('delete-selected-results');
    btn.disabled=true;btn.textContent='삭제 중…';
    try{
        await api('/api/delete',{ids:toDelete});
        selectedJobIds.clear();
        await jobs();
        $('results-notice').textContent=`${toDelete.length}개의 결과를 삭제했습니다. 파일은 로컬 휴지통에 보관됩니다.`;
    }catch(e){
        $('results-notice').textContent=e.message;
    }finally{
        syncBatchSelectionUI();
    }
};

$('jobs').addEventListener('click',async event=>{
    const button=event.target.closest('[data-delete]');
    if(!button||button.disabled)return;
    button.disabled=true;button.textContent='삭제 중…';
    try{
        await api('/api/delete',{id:button.dataset.delete});
        selectedJobIds.delete(button.dataset.delete);
        await jobs();
        $('results-notice').textContent='결과를 삭제했습니다. 파일은 로컬 휴지통에 보관됩니다.';
    }catch(e){
        $('results-notice').textContent=e.message;
        button.disabled=false;button.textContent='삭제';
    }finally{
        syncBatchSelectionUI();
    }
});

$('language').value=localStorage.getItem('music-language')||'ko';
$('language').onchange=()=>localStorage.setItem('music-language',$('language').value);
$('lyrics-example').onclick=()=>{
    $('lyrics').value='[Verse]\n창가에 내려앉은 따스한 햇살\n잠들었던 마음이 천천히 깨어나\n\n[Chorus]\n오늘도 너와 함께 걸어가\n작은 꿈을 품고 노래해';
    $('language').value='ko';
    localStorage.setItem('music-language','ko');
};
const LYRIC_REQUEST_PROMPT=[
    "당신은 AI 음악 생성 모델 'ACE-Step' 전용 작사가이자 프롬프트 엔지니어입니다.",
    "아래 [필수 작성 규칙 - 반드시 준수할 것]과 사용자가 제공하는 [곡 기획 정보]를 바탕으로 ACE-Step에서 가사 누락과 발음 깨짐 없이 완벽하게 노래할 수 있는 '영문 스타일 프롬프트'와 '한국어 가사'를 작성해 주세요.",
    "",
    "### [필수 작성 규칙 - 반드시 준수할 것]",
    "1. **음절 수 엄격 제한 (가사 누락 방지)**",
    "   - 모든 가사는 **한 줄당 공백 제외 6~10음절(3~4어절)** 이내로 짧게 끊어 작성하세요. (절대 12음절을 넘기지 마세요.)",
    "   - 1절(Verse 1)과 2절(Verse 2), 각 후렴구(Chorus)의 대응하는 줄은 음절 수와 리듬감을 동일하게 맞추세요.",
    "",
    "2. **한국어 발음 최적화 (G2P 표기 적용)**",
    "   - ACE-Step이 발음을 흘리지 않도록 **겹받침, 거센 연음, 비음화 구간은 실제 소리 나는 발음대로** 적으세요.",
    "     (예: '빛나는' → '빈나는', '같이 걸을까' → '가치 걸을까', '꽃잎이' → '꼰니피', '닿을 듯' → '다을 듯')",
    "   - 영어 단어와 숫자는 절대 알파벳이나 아라비아 숫자로 쓰지 말고 **한글 발음**으로 표기하세요. (예: 'Love' → '러브', '24시간' → '스물네 시간')",
    "   - display_lyrics(화면 표시용 정자법 가사)와 phonetic_lyrics(ACE-Step 엔진 전달용 발음 가사)를 각각 생성하여 제공",
    "",
    "3. **구조 태그 및 호흡 기호 배치**",
    "   - 가사 최상단에 `[ko]` 태그를 명시하세요.",
    "   - `[Intro]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]` 같은 곡 구조 태그를 단독 줄로 배치하고, 파트 사이에는 빈 줄을 한 줄씩 넣으세요.",
    "   - 보컬이 숨을 쉬어야 하는 짧은 휴지기에는 쉼표(`,`)를 찍고, 음을 길게 끌어야 하는 단어 끝에는 하이픈(`-`)을 붙이세요.",
    "",
    "4. **ACE-Step 영문 스타일 프롬프트 세팅**",
    "   - 가사 출력 전, 곡의 장르, 악기 구성, 분위기, 보컬 성별/음색, 정확한 템포(예: `110 BPM`)를 쉼표로 구분한 영문 태그 형태로 먼저 제시하세요.",
    "",
    "### [곡 기획 정보]",
    "- **주제 및 스토리**: (예: 퇴근길 밤거리를 걸으며 느끼는 위로와 여유)",
    "- **장르 및 분위기**: (예: 시티팝, 레트로, 몽환적인, 따뜻한)",
    "- **보컬 스타일**: (예: 부드러운 여성 보컬, 공기 반 소리 반)",
    "- **희망 템포(BPM) 및 곡 길이**: (예: 105 BPM, 약 2분 30초 분량)"
].join('\n');
$('copy-lyric-request').onclick=async()=>{
    const request=LYRIC_REQUEST_PROMPT;
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
bindModal('prompt-help-dialog','open-prompt-help',['close-prompt-help','confirm-prompt-help']);
bindModal('lyric-guide-dialog','open-lyric-guide',['close-lyric-guide','confirm-lyric-guide']);

$('copy-lyrics').onclick=async()=>{
    const text=$('lyrics').value.trim();
    const btn=$('copy-lyrics');
    if(!text){
        $('lyric-tools-status').className='api-key-status error';
        $('lyric-tools-status').textContent='복사할 가사가 비어 있습니다.';
        return;
    }
    try{
        await navigator.clipboard.writeText($('lyrics').value);
        $('lyric-tools-status').className='api-key-status success';
        $('lyric-tools-status').textContent='가사를 클립보드에 복사했습니다.';
        const origHTML=btn.innerHTML;
        btn.innerHTML=window.StudioIcons('check')+'<span>복사됨!</span>';
        setTimeout(()=>{btn.innerHTML=origHTML;},2000);
    }catch(e){
        $('lyric-tools-status').className='api-key-status error';
        $('lyric-tools-status').textContent='가사 복사 실패: '+e.message;
    }
};

let currentGeneratedLyrics={title:'',stylePrompt:'',g2pLyrics:'',standardLyrics:'',summary:''};
let activePreviewTab='standard';

function setPreviewTab(type){
    activePreviewTab=type==='g2p'?'g2p':'standard';
    const isStandard=activePreviewTab==='standard';
    $('tab-preview-standard').classList.toggle('active',isStandard);
    $('tab-preview-g2p').classList.toggle('active',!isStandard);
    $('lyric-gen-result-lyrics').value=isStandard?(currentGeneratedLyrics.standardLyrics||''):(currentGeneratedLyrics.g2pLyrics||'');
}

$('tab-preview-standard').onclick=()=>setPreviewTab('standard');
$('tab-preview-g2p').onclick=()=>setPreviewTab('g2p');

$('btn-copy-preview-lyrics').onclick=async()=>{
    const text=$('lyric-gen-result-lyrics').value.trim();
    const btn=$('btn-copy-preview-lyrics');
    if(!text)return;
    try{
        await navigator.clipboard.writeText($('lyric-gen-result-lyrics').value);
        const orig=btn.innerHTML;
        btn.innerHTML=window.StudioIcons('check')+'<span>복사됨!</span>';
        setTimeout(()=>{btn.innerHTML=orig;},2000);
    }catch(e){}
};

function updateExaoneKeyUi(isEditing=false){
    const key=(state?.settings?.exaoneApiKey||'').trim();
    if(key){
        $('exaone-key-summary').hidden=false;
        const masked=key.length>8?(key.slice(0,4)+'••••'+key.slice(-4)):key;
        $('exaone-key-summary-text').textContent=`EXAONE API 키 등록됨 (${masked})`;
        $('exaone-api-key').value=key;
        $('exaone-key-edit-panel').hidden=!isEditing;
        $('toggle-exaone-key-box').textContent=isEditing?'관리 닫기':'API 키 관리';
        if(!isEditing){
            $('exaone-key-status').textContent='';
            $('exaone-key-status').className='api-key-status';
        }
    }else{
        $('exaone-key-summary').hidden=true;
        $('exaone-api-key').value='';
        $('exaone-key-edit-panel').hidden=false;
        $('exaone-key-status').className='api-key-status';
        $('exaone-key-status').textContent='가사를 자동 생성하려면 K-EXAONE API 키를 먼저 입력하고 저장해 주세요.';
    }
}

$('toggle-exaone-key-box').onclick=()=>{
    const currentlyHidden=$('exaone-key-edit-panel').hidden;
    updateExaoneKeyUi(currentlyHidden);
};

function updateLyricPromptPlaceholder(){
    if(!$('lyric-gen-prompt')||!$('lyric-gen-lang'))return;
    const isEn=$('lyric-gen-lang').value==='en';
    $('lyric-gen-prompt').placeholder=isEn
        ?'예: A nostalgic late-night drive under neon city lights (한글로 "비 오는 밤 따뜻한 위로의 노래"처럼 적어도 영어 가사로 생성됩니다)'
        :'예: 늦은 밤 비 내리는 버스 정류장, 따뜻한 캔커피를 쥐고 하루의 피로를 털어내는 위로의 노래';
}
if($('lyric-gen-lang')){
    $('lyric-gen-lang').onchange=()=>{
        try{localStorage.setItem('lyric-gen-lang',$('lyric-gen-lang').value);}catch(e){}
        updateLyricPromptPlaceholder();
    };
}
const lyricCustomOptions=[
    {selectId:'lyric-gen-genre',inputId:'lyric-gen-genre-custom',fallback:'종교음악'},
    {selectId:'lyric-gen-mood',inputId:'lyric-gen-mood-custom',fallback:'따뜻함/편안함'},
    {selectId:'lyric-gen-voice',inputId:'lyric-gen-voice-custom',fallback:'청아한 여성'},
    {selectId:'lyric-gen-tempo',inputId:'lyric-gen-tempo-custom',fallback:'적당하고 편안하게 (약 95~110 BPM)'}
];
const getLyricOptionValue=(selectId,inputId,fallback)=>{
    const sel=$(selectId);
    if(!sel)return '';
    if(sel.value==='__custom__'){
        const inp=$(inputId);
        return(inp&&inp.value.trim())?inp.value.trim():fallback;
    }
    return sel.value;
};

bindModal('lyric-generator-dialog','open-lyric-generator',['close-lyric-gen','close-lyric-gen-after'],()=>{
    updateExaoneKeyUi(false);
    if($('lyric-gen-lang')&&$('language')){
        const currentMusicLang=$('language').value==='en'?'en':'ko';
        let savedLang=null;
        try{savedLang=localStorage.getItem('lyric-gen-lang');}catch(e){}
        $('lyric-gen-lang').value=(savedLang||currentMusicLang)==='en'?'en':'ko';
    }
    updateLyricPromptPlaceholder();
    lyricCustomOptions.forEach(({selectId,inputId})=>{
        const sel=$(selectId);
        const inp=$(inputId);
        if(sel&&inp){
            inp.hidden=sel.value!=='__custom__';
        }
    });
    $('submit-lyric-gen').classList.remove('is-loading');
    $('submit-lyric-gen').disabled=false;
    $('submit-lyric-gen').innerHTML=window.StudioIcons('sparkles')+' <span>가사 및 스타일 생성하기</span>';
    $('lyric-gen-status').textContent='';
    $('lyric-gen-status').className='';
});

lyricCustomOptions.forEach(({selectId,inputId})=>{
    const sel=$(selectId);
    const inp=$(inputId);
    if(sel&&inp){
        sel.addEventListener('change',()=>{
            const isCustom=sel.value==='__custom__';
            inp.hidden=!isCustom;
            if(isCustom)inp.focus();
        });
    }
});
$('save-exaone-key').onclick=async()=>{
    const key=$('exaone-api-key').value.trim();
    const status=$('exaone-key-status');
    const button=$('save-exaone-key');
    if(!key){status.className='api-key-status error';status.textContent='API 키를 입력해 주세요.';return;}
    button.disabled=true;status.className='api-key-status';
    status.innerHTML=window.StudioIcons('spinner','ui-icon-spin')+' API 키 연결 확인 중…';
    try{
        await api('/api/lyrics/test',{apiKey:key});
        const current=state?.settings?{...state.settings}:{policy:'auto',mode:'song'};
        current.exaoneApiKey=key;
        const res=await api('/api/settings',current);
        if(state)state.settings=res.settings;
        status.className='api-key-status success';status.textContent='API 키가 확인되었으며 안전하게 저장되었습니다.';
        setTimeout(()=>{updateExaoneKeyUi(false);},700);
    }catch(e){status.className='api-key-status error';status.textContent=e.message;}
    finally{button.disabled=false;}
};
$('delete-exaone-key').onclick=async()=>{
    const status=$('exaone-key-status');
    const button=$('delete-exaone-key');
    button.disabled=true;
    try{
        const current=state?.settings?{...state.settings}:{policy:'auto',mode:'song'};
        current.exaoneApiKey='';
        const res=await api('/api/settings',current);
        if(state)state.settings=res.settings;
        $('exaone-api-key').value='';
        updateExaoneKeyUi(true);
        status.className='api-key-status success';
        status.textContent='등록된 API 키가 삭제되었습니다.';
    }catch(e){status.className='api-key-status error';status.textContent='삭제 실패: '+e.message;}
    finally{button.disabled=false;}
};
if($('lyric-gen-timeout')){
    $('lyric-gen-timeout').onchange=async()=>{
        const timeoutVal=parseInt($('lyric-gen-timeout').value,10);
        const current=state?.settings?{...state.settings}:{policy:'auto',mode:'song'};
        current.exaoneTimeout=isNaN(timeoutVal)?600:timeoutVal;
        try{
            const res=await api('/api/settings',current);
            if(state)state.settings=res.settings;
        }catch(e){console.error('Failed to save exaoneTimeout',e);}
    };
}
$('submit-lyric-gen').onclick=async()=>{
    const prompt=$('lyric-gen-prompt').value.trim();
    const status=$('lyric-gen-status');
    const button=$('submit-lyric-gen');
    const apiKey=$('exaone-api-key').value.trim()||state?.settings?.exaoneApiKey;
    if(!apiKey){
        updateExaoneKeyUi(true);
        status.className='api-key-status error';status.textContent='위 입력창에 EXAONE API 키를 먼저 입력하고 저장해 주세요.';
        $('exaone-api-key').focus();return;
    }
    if(!prompt){
        status.className='api-key-status error';status.textContent='곡 주제나 이야기를 입력해 주세요.';
        $('lyric-gen-prompt').focus();return;
    }
    const langSelect=$('lyric-gen-lang');
    const lang=(langSelect?langSelect.value:'ko')==='en'?'en':'ko';
    const isEn=(lang==='en');
    const langStr=isEn?'영문':'한국어';
    const timeoutSelect=$('lyric-gen-timeout');
    const parsedTimeout=timeoutSelect?parseInt(timeoutSelect.value,10):600;
    const timeoutVal=isNaN(parsedTimeout)?600:parsedTimeout;
    button.disabled=true;
    button.classList.add('is-loading');
    status.className='';
    status.textContent='';
    let elapsed=0;
    const updateProgress=()=>{
        const limitStr=timeoutVal===0?'대기 제한 없음':`최대 ${timeoutVal}초 대기`;
        button.innerHTML=window.StudioIcons('spinner','ui-icon-spin')+` <span>K-EXAONE 2.5가 ${langStr} 가사를 생성하고 있습니다… (${formatDuration(elapsed)} 경과 · ${limitStr})</span>`;
    };
    updateProgress();
    const timer=setInterval(()=>{elapsed++;updateProgress();},1000);
    try{
        const resp=await api('/api/lyrics/generate',{
            prompt:prompt,
            genre:getLyricOptionValue('lyric-gen-genre','lyric-gen-genre-custom','종교음악'),
            mood:getLyricOptionValue('lyric-gen-mood','lyric-gen-mood-custom','따뜻함/편안함'),
            voice:getLyricOptionValue('lyric-gen-voice','lyric-gen-voice-custom','청아한 여성'),
            tempo:getLyricOptionValue('lyric-gen-tempo','lyric-gen-tempo-custom','적당하고 편안하게 (약 95~110 BPM)'),
            language:lang,
            apiKey:apiKey,
            timeout:timeoutVal
        });
        const data=resp.data;
        currentGeneratedLyrics={
            title:data.title||'',
            stylePrompt:data.stylePrompt||'',
            g2pLyrics:data.lyrics||'',
            standardLyrics:data.standardLyrics||data.displayLyrics||data.lyrics||'',
            summary:data.summary||(isEn?'ACE-Step 맞춤 영문 가사 완성':'ACE-Step 맞춤 가사 완성'),
            language:data.language||lang
        };
        $('lyric-gen-result').hidden=false;
        $('lyric-gen-result-title').value=currentGeneratedLyrics.title;
        $('lyric-gen-result-style').value=currentGeneratedLyrics.stylePrompt;
        $('lyric-gen-result-summary').textContent=currentGeneratedLyrics.summary;

        if(isEn){
            $('tab-preview-standard').textContent='영문 표준 가사';
            $('tab-preview-g2p').textContent='보컬 엔진 가사 ([en])';
        }else{
            $('tab-preview-standard').textContent='정음 가사 (표준 맞춤법)';
            $('tab-preview-g2p').textContent='G2P 발음 표기 (소리 나는 대로)';
        }

        setPreviewTab('standard');

        status.className='api-key-status success';
        status.textContent=`${langStr} 가사와 스타일 생성이 완료되었습니다 (${elapsed}초 소요). 아래 미리보기를 확인하고 적용하세요.`;
    }catch(e){
        status.className='api-key-status error';
        status.textContent=e.message;
    }finally{
        clearInterval(timer);
        button.classList.remove('is-loading');
        button.disabled=false;
        button.innerHTML=window.StudioIcons('sparkles')+' <span>가사 및 스타일 생성하기</span>';
    }
};
$('apply-lyric-gen').onclick=()=>{
    const title=$('lyric-gen-result-title').value.trim();
    const style=$('lyric-gen-result-style').value.trim();
    const isG2P=(activePreviewTab==='g2p');
    const chosenLyrics=isG2P?currentGeneratedLyrics.g2pLyrics:currentGeneratedLyrics.standardLyrics;
    const genLang=currentGeneratedLyrics.language||'ko';

    if(title&&!$('track-title').value){$('track-title').value=title;}
    if(chosenLyrics){$('lyrics').value=chosenLyrics;}
    if(style){$('prompt').value=style;updatePromptCount();}
    if($('language')){
        $('language').value=genLang;
        try{localStorage.setItem('music-language',genLang);}catch(e){}
    }
    render();
    $('lyric-generator-dialog').close();

    $('lyric-tools-status').className='api-key-status success';
    if(genLang==='en'){
        $('lyric-tools-status').textContent='영문 곡 제목/가사와 음악 설명이 작업창에 적용되었습니다. (보컬 언어: 영어)';
    }else if(isG2P){
        $('lyric-tools-status').textContent='G2P 발음 가사와 음악 설명이 작업창에 적용되었습니다. (보컬 언어: 한국어)';
    }else{
        $('lyric-tools-status').textContent='정음(표준 맞춤법) 가사와 음악 설명이 작업창에 적용되었습니다. (보컬 언어: 한국어)';
    }
};
$('paypal-sponsor').onclick=async()=>{
    const button=$('paypal-sponsor'),status=$('sponsor-status');
    button.disabled=true;status.textContent='기본 웹브라우저를 열고 있습니다…';
    try{await api('/api/sponsor/paypal',{});status.textContent='기본 웹브라우저에서 PayPal 후원 페이지를 열었습니다.';}
    catch(error){status.textContent=error.message;}
    finally{button.disabled=false;}
};
