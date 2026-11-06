/* Composable music descriptions; preserve free text and manage only inserted phrases. */
(()=>{
    const data={
        genre:{label:'장르 및 음악 스타일',items:[
            ['ballad','감성 발라드','ballad, emotional and expressive singing style, soft and heartfelt vocal tone','emotional instrumental ballad, soft piano, heartfelt melodies'],
            ['pop','신나는 팝/댄스','pop and dance music, energetic and upbeat pop vocals, dynamic rhythm, bright and clean tone','upbeat pop and dance music, dynamic rhythm, bright and clean instrumental sound'],
            ['rnb','힙합/알앤비','hip-hop and R&B, smooth and soulful R&B rhythm, rhythmic and groovy vocal delivery','hip-hop and R&B instrumental, soulful chords, smooth bass and groovy beats'],
            ['acoustic','어쿠스틱/인디','acoustic indie, intimate and raw indie vocal tone, natural and warm acoustic vibe','warm acoustic indie instrumental, natural acoustic guitar and intimate arrangement'],
            ['rock','웅장한 록/메탈','epic rock and metal, powerful and gritty rock vocals, strong projection, high energy','epic rock and metal instrumental, powerful electric guitars, energetic drums'],
            ['jazz','재즈/라운지','jazz lounge, relaxed and sophisticated vocals, warm piano and upright bass','relaxed jazz lounge instrumental, warm piano, brushed drums and upright bass'],
            ['lofi','로파이','lofi pop, mellow intimate vocals, soft drums and warm piano','mellow lofi instrumental, soft drums, warm piano and gentle textures'],
            ['ambient','앰비언트','ambient pop, soft floating vocals, spacious synthesizer pads','spacious ambient instrumental, slow evolving synthesizer pads and gentle textures'],
            ['cinematic','시네마틱/오케스트라','cinematic orchestral song, expressive vocals, sweeping strings and a dramatic arrangement','cinematic orchestral instrumental, sweeping strings and a dramatic arrangement'],
            ['electronic','일렉트로닉/신스팝','electronic synth-pop, clear melodic vocals, pulsing synths and a steady beat','electronic synth-pop instrumental, pulsing synths and a steady beat'],
            ['trot','트로트','Korean trot, expressive melodic vocals, lilting rhythm and warm nostalgic arrangement','Korean trot instrumental, lilting rhythm and warm nostalgic arrangement']
        ]},
        voice:{label:'보컬 음색 프로필',vocalOnly:true,items:[
            ['bright-female','청아한 여성','clear and sweet female vocal, airy and high-pitched tone'],
            ['mature-female','성숙한 여성','deep and resonant female vocal, velvety and smooth tone'],
            ['soft-male','감미로운 남성','gentle and warm male vocal, romantic and soothing tone'],
            ['husky-male','허스키 남성','husky and raspy male voice, deep and powerful vocal texture'],
            ['youthful','소년/소녀','young and youthful singing voice, bright and cheerful delivery'],
            ['baritone','풍부한 남성 중저음','rich baritone male vocal, rounded low register and gentle resonance'],
            ['neutral','맑고 담백한 중성 음색','clear and neutral vocal character, understated and natural delivery']
        ]},
        mood:{label:'감정선 및 무드',items:[
            ['sad','애절함/슬픔','sorrowful and tearful singing voice, full of melancholy and deep emotion','sorrowful instrumental mood, melancholy melodies and deep emotion'],
            ['joyful','밝고 신남','joyful and smiling vocal tone, full of happiness and bright energy','joyful instrumental mood, cheerful melodies and bright energy'],
            ['dreamy','몽환적/신비로움','dreamy and ethereal vocal with a soft reverb-like quality, mysterious tone','dreamy and ethereal instrumental textures, spacious reverb and a mysterious mood'],
            ['passionate','열정적/강렬함','passionate and intense vocal delivery, fierce and emotional projection','passionate instrumental mood, intense rhythms and a dramatic build'],
            ['warm','따뜻함/편안함','warm and comforting vocal delivery, gentle and reassuring emotion','warm and comforting instrumental mood, gentle melodies and a relaxed atmosphere'],
            ['hopeful','희망/벅찬 감동','hopeful and uplifting vocals, a growing sense of wonder and inspiration','hopeful uplifting instrumental mood, a growing sense of wonder and inspiration'],
            ['calm','차분함/집중','calm and restrained vocals, peaceful and unhurried emotion','calm and peaceful instrumental mood, restrained melodies suitable for focus']
        ]},
        tempo:{label:'템포',items:[
            ['slow','느리고 차분하게','slow and measured singing pace, long and sustained notes','slow and measured instrumental pace, long sustained notes'],
            ['medium','적당하고 편안하게','moderate tempo, relaxed and steady vocal phrasing','moderate instrumental tempo, relaxed and steady rhythm'],
            ['fast','빠르고 경쾌하게','fast and crisp vocal delivery, sharp and rhythmic pacing','fast and lively instrumental tempo, crisp and rhythmic pacing']
        ]},
        technique:{label:'창법 및 테크닉',vocalOnly:true,items:[
            ['speech','말하듯이 노래하기','conversational and natural singing style, speaking tone blended with melody'],
            ['legato','부드럽게 이어 부르기','smooth legato singing, connected phrases and gentle transitions'],
            ['diction','또렷한 가사 전달','clear diction and intelligible lyrics, precise but natural vocal articulation'],
            ['vibrato','은은한 비브라토','subtle natural vibrato on sustained notes, controlled and expressive singing'],
            ['harmony','부드러운 화음/코러스','gentle supporting vocal harmonies, clear lead vocal and restrained backing vocals']
        ]}
    };
    const input=document.getElementById('prompt');
    const fields=document.getElementById('preset-fields');
    const status=document.getElementById('preset-status');
    const selected=Object.fromEntries(Object.keys(data).map(key=>[key,'']));
    let currentMode='bgm',appliedBlock='';
    for(const [key,group] of Object.entries(data)){
        const field=document.createElement('div');field.className='preset-field';field.dataset.presetGroup=key;
        const label=document.createElement('label');label.htmlFor='preset-'+key;label.textContent=group.label;
        const select=document.createElement('select');select.id='preset-'+key;
        select.add(new Option('선택 안 함',''));
        group.items.forEach(([value,name])=>select.add(new Option(name,value)));
        select.onchange=()=>{
            const old=selected[key];selected[key]=select.value;
            if(!compose()){selected[key]=old;select.value=old;}
        };
        field.append(label,select);fields.append(field);
    }
    function phrases(){
        const result=[];
        for(const [key,group] of Object.entries(data)){
            if(group.vocalOnly&&currentMode!=='song')continue;
            const item=group.items.find(item=>item[0]===selected[key]);
            if(item)result.push(currentMode==='song'?item[2]:item[3]);
        }
        if(result.length&&currentMode==='bgm')result.push('instrumental, no vocals');
        return result;
    }
    function refreshFields(){
        for(const [key,group] of Object.entries(data)){
            const select=document.getElementById('preset-'+key);
            select.value=selected[key];
            const hidden=group.vocalOnly&&currentMode!=='song';
            select.parentElement.hidden=hidden;select.disabled=hidden;
        }
        document.querySelectorAll('[data-preset-genre]').forEach(button=>{
            button.setAttribute('aria-pressed',String(selected.genre===button.dataset.presetGenre));
        });
        document.getElementById('preset-mode-help').textContent=currentMode==='song'
            ?'항목별로 하나씩 조합하세요. 템포와 창법은 함께 선택할 수 있습니다.'
            :'배경음악에서는 보컬 음색과 창법을 제외한 연주용 표현을 입력합니다.';
    }
    function updateStatus(message='',isError=false){
        const max=currentMode==='song'?512:2000;
        status.textContent=message||`음악 설명 ${input.value.length} / ${max}자 · 직접 쓴 설명도 유지됩니다.`;
        status.classList.toggle('preset-error',input.value.length>max||isError);
    }
    function compose(allowOverLimit=false){
        const base=appliedBlock&&input.value.includes(appliedBlock)?input.value.replace(appliedBlock,''):input.value;
        const parts=phrases();
        const block=parts.length?(base.length?'\n\n':'')+'Style: '+parts.join('; ')+'.':'';
        const value=base+block,max=currentMode==='song'?512:2000;
        if(value.length>max&&!allowOverLimit){
            updateStatus(`설명이 ${max}자를 넘게 됩니다. 직접 입력한 설명을 줄인 뒤 다시 선택해 주세요.`,true);
            return false;
        }
        input.value=value;appliedBlock=block;refreshFields();updateStatus();return true;
    }
    input.addEventListener('input',()=>{
        if(appliedBlock&&!input.value.includes(appliedBlock)){
            appliedBlock='';Object.keys(selected).forEach(key=>selected[key]='');refreshFields();
            updateStatus('수정한 문구는 직접 쓴 설명으로 유지합니다. 프리셋을 새로 조합할 수 있습니다.');
        }else updateStatus();
    });
    document.querySelectorAll('[data-preset-genre]').forEach(button=>button.onclick=()=>{
        const old=selected.genre;selected.genre=old===button.dataset.presetGenre?'':button.dataset.presetGenre;
        if(!compose()){selected.genre=old;refreshFields();}
    });
    document.getElementById('clear-presets').onclick=()=>{
        Object.keys(selected).forEach(key=>selected[key]='');compose(true);
    };
    window.MusicPresets={
        setMode(mode){if(mode===currentMode)return;currentMode=mode;compose(true);},
        reset(){appliedBlock='';Object.keys(selected).forEach(key=>selected[key]='');refreshFields();updateStatus();}
    };
    refreshFields();updateStatus();
})();
