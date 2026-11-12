/* ACE-Step 1.5 expert quality controls: collapsed panel, presets, defaults and per-item help dialog. */
(()=>{
    const $=id=>document.getElementById(id);
    const icon=(name)=>window.StudioIcons(name);
    const STORAGE='song-expert-settings';
    const DEFAULTS={inferenceSteps:8,shift:3.0,inferMethod:'ode',sampler:'euler',dcw:true,lmTemperature:0.85,lmCfgScale:2.0,lmTopP:0.9};
    const PRESETS=[
        {id:'default',name:'기본 · 균형',desc:'소리숲 기본값. 속도와 품질의 균형이 가장 좋습니다.',values:{}},
        {id:'fast',name:'빠른 초안',desc:'단계를 줄여 아이디어를 빨리 들어볼 때 사용합니다.',values:{inferenceSteps:6}},
        {id:'hifi',name:'고음질',desc:'단계와 2차 샘플러로 디테일을 높입니다. 생성 시간이 약 2~3배 늘어납니다.',values:{inferenceSteps:12,sampler:'heun'}},
        {id:'stable',name:'안정적 구성',desc:'설명과 가사를 더 충실히 따르고 튀는 전개를 줄입니다.',values:{lmTemperature:0.7,lmCfgScale:2.5,lmTopP:0.85}}
    ];
    const FIELDS=[
        {key:'inferenceSteps',group:'음질 · 확산 모델',label:'확산 단계 수',type:'range',min:4,max:20,step:1,format:v=>v+'단계',
         help:['노래 소리를 다듬는 반복 횟수입니다.','ACE-Step 1.5 Turbo 모델은 8단계에 맞춰 학습되어 기본값이 가장 안정적입니다. 값을 높이면 디테일이 조금 늘 수 있지만 생성 시간이 단계 수에 비례해 늘어나고, 너무 높으면 오히려 소리가 과하게 매끈해질 수 있습니다. 값을 낮추면 빨라지지만 잡음과 뭉개짐이 늘어납니다.','권장: 6~12 · 기본 8']},
        {key:'shift',group:'음질 · 확산 모델',label:'타임스텝 시프트',type:'range',min:1,max:5,step:0.1,format:v=>Number(v).toFixed(1),
         help:['확산 단계를 어느 구간에 집중할지 정합니다.','값이 높을수록 초반 큰 구조(리듬, 화성)에 단계를 더 쓰고, 낮을수록 후반 세부 질감(음색, 고음역)에 더 씁니다. Turbo 모델은 3.0에 맞춰져 있습니다.','권장: 2.5~4.0 · 기본 3.0']},
        {key:'inferMethod',group:'음질 · 확산 모델',label:'확산 방식',type:'select',options:[['ode','ODE · 결정적, 깨끗함'],['sde','SDE · 확률적, 질감 풍부']],
         help:['확산 계산에 무작위성을 섞을지 정합니다.','ODE는 같은 조건에서 깨끗하고 일관된 결과를 냅니다. SDE는 단계마다 약간의 무작위성을 더해 질감이 풍부해질 수 있지만 잡음이 늘 수도 있습니다.','권장: ODE · 기본 ODE']},
        {key:'sampler',group:'음질 · 확산 모델',label:'샘플러',type:'select',options:[['euler','Euler · 1차, 빠름'],['heun','Heun · 2차, 정밀']],
         help:['각 단계를 계산하는 수치 방식입니다.','Heun은 단계마다 보정 계산을 한 번 더 해 오차가 적고 디테일이 좋아질 수 있지만, 생성 시간이 약 2배 늘어납니다.','권장: Euler(일반), Heun(최종본) · 기본 Euler']},
        {key:'dcw',group:'음질 · 확산 모델',label:'웨이블릿 보정(DCW)',type:'toggle',
         help:['주파수 대역별로 결과를 미세 보정하는 기능입니다.','Turbo 모델에서 저음과 고음의 뭉개짐을 줄여 선명도를 높이도록 조정된 기능입니다. 특별한 이유가 없다면 켜 두세요. 소리가 지나치게 날카롭게 느껴질 때만 꺼 보세요.','권장: 켬 · 기본 켬']},
        {key:'lmTemperature',group:'곡 구성 · 플래너 모델',label:'구성 다양성',type:'range',min:0.3,max:1.5,step:0.05,format:v=>Number(v).toFixed(2),
         help:['가사와 설명을 바탕으로 곡 구성(멜로디 흐름, 박자, 조성)을 계획할 때의 무작위성입니다.','값이 낮으면 무난하고 예측 가능한 구성이, 높으면 독창적이지만 가끔 어색한 전개가 나옵니다.','권장: 0.7~1.0 · 기본 0.85']},
        {key:'lmCfgScale',group:'곡 구성 · 플래너 모델',label:'설명 반영 강도',type:'range',min:1,max:4,step:0.1,format:v=>Number(v).toFixed(1),
         help:['음악 설명과 네거티브 프롬프트를 얼마나 강하게 따를지 정합니다.','값을 높이면 장르·분위기 설명을 더 충실히 따르지만, 너무 높으면 표현이 경직되거나 부자연스러워질 수 있습니다.','권장: 1.5~3.0 · 기본 2.0']},
        {key:'lmTopP',group:'곡 구성 · 플래너 모델',label:'후보 범위(Top-p)',type:'range',min:0.5,max:1,step:0.01,format:v=>Number(v).toFixed(2),
         help:['곡을 계획할 때 고려하는 후보의 범위입니다.','값이 낮으면 가능성 높은 후보만 골라 안정적이고, 높으면 드문 후보까지 고려해 다양해집니다.','권장: 0.85~0.95 · 기본 0.9']}
    ];
    let values={...DEFAULTS};
    function clean(input){
        const out={...DEFAULTS};
        if(!input||typeof input!=='object')return out;
        for(const f of FIELDS){
            const v=input[f.key];if(v===undefined)continue;
            if(f.type==='toggle'){if(typeof v==='boolean')out[f.key]=v;}
            else if(f.type==='select'){if(f.options.some(([o])=>o===v))out[f.key]=v;}
            else if(typeof v==='number'&&Number.isFinite(v)&&v>=f.min&&v<=f.max)out[f.key]=f.step===1?Math.round(v):Math.round(v*100)/100;
        }
        return out;
    }
    const same=(a,b)=>FIELDS.every(f=>a[f.key]===b[f.key]);
    const presetValues=p=>clean({...DEFAULTS,...p.values});
    function save(){try{localStorage.setItem(STORAGE,JSON.stringify(values));}catch(e){}}
    function summary(){
        const preset=PRESETS.find(p=>same(presetValues(p),values));
        $('expert-summary').textContent=preset?preset.name:'사용자 지정';
        $('expert-reset').disabled=same(values,DEFAULTS);
        for(const b of $('expert-presets').querySelectorAll('button'))b.setAttribute('aria-pressed',String(preset?.id===b.dataset.preset));
    }
    function sync(){
        for(const f of FIELDS){
            const el=$('expert-'+f.key);if(!el)continue;
            if(f.type==='toggle')el.checked=values[f.key];
            else el.value=String(values[f.key]);
            if(f.type==='range')$('expert-'+f.key+'-value').textContent=f.format(values[f.key]);
        }
        summary();
    }
    function set(next){values=clean(next);save();sync();}
    function openHelp(f){
        $('expert-help-title').textContent=f.label;
        const [lead,body,tip]=f.help;
        $('expert-help-lead').textContent=lead;$('expert-help-body').textContent=body;$('expert-help-tip').textContent=tip;
        $('expert-help-dialog').showModal();
    }
    function build(){
        const root=$('expert-settings');if(!root||root.dataset.ready)return;root.dataset.ready='1';
        $('expert-toggle').insertAdjacentHTML('afterbegin',icon('sliders'));
        $('expert-toggle').insertAdjacentHTML('beforeend',icon('chevron','expert-chevron'));
        $('expert-reset').insertAdjacentHTML('afterbegin',icon('refresh'));
        $('expert-toggle').onclick=()=>{const open=$('expert-body').hidden;$('expert-body').hidden=!open;$('expert-toggle').setAttribute('aria-expanded',String(open));root.classList.toggle('is-open',open);};
        $('expert-reset').onclick=()=>set(DEFAULTS);
        const presets=$('expert-presets');
        for(const p of PRESETS){
            const b=document.createElement('button');b.type='button';b.className='expert-preset';b.dataset.preset=p.id;
            const name=document.createElement('b'),desc=document.createElement('small');name.textContent=p.name;desc.textContent=p.desc;b.append(name,desc);
            b.onclick=()=>set(presetValues(p));presets.append(b);
        }
        const fields=$('expert-fields');let group='';
        for(const f of FIELDS){
            if(f.group!==group){group=f.group;const h=document.createElement('h3');h.className='expert-group';h.textContent=group;fields.append(h);}
            const row=document.createElement('div');row.className='expert-field expert-'+f.type;
            const head=document.createElement('div');head.className='expert-field-head';
            const label=document.createElement('label');label.htmlFor='expert-'+f.key;label.textContent=f.label;
            const help=document.createElement('button');help.type='button';help.className='prompt-help-button expert-help';
            help.setAttribute('aria-label',f.label+' 설명 보기');help.setAttribute('aria-haspopup','dialog');help.title=f.label+' 설명';help.innerHTML=icon('help');help.onclick=()=>openHelp(f);
            head.append(label,help);
            let input;
            if(f.type==='range'){
                const out=document.createElement('output');out.id='expert-'+f.key+'-value';out.htmlFor='expert-'+f.key;head.append(out);
                input=document.createElement('input');input.type='range';input.min=f.min;input.max=f.max;input.step=f.step;
                input.oninput=()=>set({...values,[f.key]:Number(input.value)});
            }else if(f.type==='select'){
                input=document.createElement('select');
                for(const [v,t] of f.options){const o=document.createElement('option');o.value=v;o.textContent=t;input.append(o);}
                input.onchange=()=>set({...values,[f.key]:input.value});
            }else{
                input=document.createElement('input');input.type='checkbox';input.setAttribute('role','switch');
                input.onchange=()=>set({...values,[f.key]:input.checked});
                label.prepend(input);
            }
            input.id='expert-'+f.key;
            row.append(head);if(f.type!=='toggle')row.append(input);fields.append(row);
        }
        $('close-expert-help').onclick=$('confirm-expert-help').onclick=()=>$('expert-help-dialog').close();
        $('expert-help-dialog').addEventListener('click',e=>{if(e.target===$('expert-help-dialog'))$('expert-help-dialog').close();});
        try{values=clean(JSON.parse(localStorage.getItem(STORAGE)||'null'));}catch(e){values={...DEFAULTS};}
        sync();
    }
    window.ExpertSettings={
        DEFAULTS:{...DEFAULTS},PRESETS,
        value:()=>({...values}),
        load:(input)=>{build();if(input)set(input);},
        set:(input)=>{build();set(input);},
        reset:()=>{build();set(DEFAULTS);},
        render:(mode)=>{build();$('expert-settings').hidden=mode!=='song';}
    };
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build);else build();
})();
