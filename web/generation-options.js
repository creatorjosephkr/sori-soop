/* Optional exclusions and instrumental tempo; each music type keeps its own draft. */
(()=>{
    const $=id=>document.getElementById(id);
    const common=[
        ['low quality','낮은 음질','전체적으로 거칠거나 품질이 낮은 소리를 줄입니다.'],
        ['muddy mix','뭉개진 믹스','악기와 소리가 겹쳐 불분명해지는 현상을 줄입니다.'],
        ['clipping','클리핑','소리가 너무 커서 찢어지는 현상을 줄입니다.'],
        ['distortion','왜곡','원치 않는 일그러진 소리를 줄입니다. 록 기타의 의도된 왜곡에도 영향을 줄 수 있습니다.'],
        ['harsh high frequencies','날카로운 고음','귀를 찌르는 듯한 고음을 줄입니다.'],
        ['background noise','배경 잡음','음악 외의 불필요한 주변 잡음을 줄입니다.'],
        ['hiss','쉬익거리는 잡음','지속적인 고주파 잡음을 줄입니다. 로파이 질감에도 영향을 줄 수 있습니다.'],
        ['hum','웅웅거리는 잡음','전기 잡음처럼 낮게 울리는 소리를 줄입니다.'],
        ['muffled audio','먹먹한 소리','답답하고 선명하지 않은 소리를 줄입니다.']
    ];
    const music=[
        ['out of tune','음정 불안정','악기의 음정이 어긋나는 현상을 줄입니다.'],
        ['arrhythmia','불규칙한 박자','의도하지 않은 박자 흐트러짐을 줄입니다. 자유로운 리듬에는 사용을 피하세요.'],
        ['sudden silence','갑작스러운 무음','곡 중간이 뜻밖에 끊겨 조용해지는 현상을 줄입니다.'],
        ['abrupt cut','갑작스러운 종료','음악이 끝에서 뚝 끊기는 현상을 줄입니다.']
    ];
    const instrumental=[['vocals, singing, speech','보컬·말소리','연주곡에 가창이나 사람의 말소리가 섞이는 것을 줄입니다.']];
    const vocal=[
        ['robotic voice','기계적인 보컬','로봇처럼 부자연스러운 목소리를 줄입니다.'],
        ['slurred pronunciation','불분명한 발음','가사를 뭉개거나 흐리게 발음하는 현상을 줄입니다.'],
        ['gibberish','의미 없는 발성','가사 대신 알아듣기 어려운 말을 부르는 현상을 줄입니다.']
    ];
    const drafts={};
    let key='bgm';
    function options(type){return [...common,...(type==='sfx'?[]:music),...(type==='song'?vocal:type==='sfx'?[]:instrumental)];}
    function draft(type=key){
        const defaults=options(type).filter(()=>type!=='sfx').map(([value])=>value);
        return drafts[type]||(drafts[type]={negative:new Set(defaults),bpm:'',custom:'',customNegative:''});
    }
    function negative(type=key){
        const selected=options(type).filter(([value])=>draft(type).negative?.has(value)).map(([value])=>value);
        const custom=(draft(type).customNegative||'').trim();
        if(custom)selected.push(custom);
        return selected.join(', ');
    }
    function renderNegative(){
        const list=$('negative-options');list.replaceChildren();
        for(const [value,title,description] of options(key)){
            const label=document.createElement('label');label.className='negative-option';
            const input=document.createElement('input');input.type='checkbox';input.checked=draft().negative.has(value);
            const text=document.createElement('span'),name=document.createElement('b'),help=document.createElement('small');
            name.textContent=title;help.textContent=description;text.append(name,help);label.append(input,text);list.append(label);
            input.onchange=()=>{if(input.checked)draft().negative.add(value);else draft().negative.delete(value);summary();};
        }
        if($('negative-custom'))$('negative-custom').value=draft().customNegative||'';
        summary();
    }
    function summary(){
        const count=draft().negative.size;
        const hasCustom=Boolean((draft().customNegative||'').trim());
        let text='네거티브 프롬프트 · ';
        if(count&&hasCustom)text+=`${count}개 선택 + 직접 입력`;
        else if(count)text+=`${count}개 선택`;
        else if(hasCustom)text+='직접 입력';
        else text+='사용 안 함';
        $('negative-summary').textContent=text;
    }
    function render(mode,isInstrumental){
        const next=mode==='song'?(isInstrumental?'instrumental':'song'):mode;
        if(next!==key){key=next;renderNegative();}
        const tempoSection=$('tempo-options');
        const tempoAnchor=document.querySelector(isInstrumental?'label[for="track-title"]':'.composer > details.prompt-presets');
        if(tempoAnchor&&tempoSection.nextElementSibling!==tempoAnchor)tempoAnchor.before(tempoSection);
        $('tempo-options').hidden=!(mode==='bgm'||isInstrumental);
        $('music-bpm').value=draft().bpm;$('music-bpm-custom').value=draft().custom;
        $('custom-bpm-wrap').hidden=draft().bpm!=='custom';
        if($('negative-custom'))$('negative-custom').value=draft().customNegative||'';
        preview();
    }
    function bpm(){
        if($('tempo-options').hidden)return null;
        const value=draft().bpm==='custom'?draft().custom:draft().bpm;
        if(draft().bpm==='')return null;
        if(!/^\d+$/.test(value)||Number(value)<30||Number(value)>300)throw Error('속도를 30~300 BPM 사이의 정수로 입력하세요.');
        return Number(value);
    }
    function prompt(source){
        const tempo=bpm();let result=source.trim();
        if(!result)throw Error('음악 설명을 입력하세요.');
        if(tempo!==null){
            const matches=[...result.matchAll(/(?:\bBPM\s*[:=]?\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*BPM\b)/gi)];
            if(matches.some(match=>Number(match[1]||match[2])!==tempo))throw Error('음악 설명의 BPM과 선택한 속도가 다릅니다. 같은 BPM으로 맞추거나 설명의 BPM을 지워 주세요.');
            if(!matches.length)result+='\nTempo: '+tempo+' BPM.';
        }
        if(result.length>2000)throw Error('BPM을 포함한 음악 설명이 2,000자를 넘습니다. 설명을 줄여 주세요.');
        return result;
    }
    function preview(){
        try{const tempo=bpm();$('bpm-preview').textContent=tempo===null?'선택하지 않으면 음악 설명에 따라 속도를 정합니다.':'생성 시 음악 설명에 '+tempo+' BPM을 합쳐 전달합니다.';}
        catch(error){$('bpm-preview').textContent=error.message;}
    }
    $('music-bpm').onchange=()=>{draft().bpm=$('music-bpm').value;$('custom-bpm-wrap').hidden=draft().bpm!=='custom';preview();};
    $('music-bpm-custom').oninput=()=>{draft().custom=$('music-bpm-custom').value;preview();};
    if($('negative-custom'))$('negative-custom').oninput=()=>{draft().customNegative=$('negative-custom').value;summary();};
    function reset(){for(const type of Object.keys(drafts))delete drafts[type];$('negative-options-details').open=false;renderNegative();$('music-bpm').value='';$('music-bpm-custom').value='';$('custom-bpm-wrap').hidden=true;if($('negative-custom'))$('negative-custom').value='';preview();}
    window.GenerationOptions={render,negative,prompt,reset};
    reset();
})();
