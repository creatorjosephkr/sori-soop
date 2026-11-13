/* Composable music descriptions; preserve free text and manage only inserted phrases. */
(()=>{
    const data={
        genre:{label:'장르 및 음악 스타일',musicOnly:true,items:[
            ['ballad','감성 발라드','ballad, emotional and expressive singing style, soft and heartfelt vocal tone','emotional instrumental ballad, soft piano, heartfelt melodies'],
            ['pop','신나는 팝/댄스','pop and dance music, energetic and upbeat pop vocals, dynamic rhythm, bright and clean tone','upbeat pop and dance music, dynamic rhythm, bright and clean instrumental sound'],
            ['ccm','CCM/기독교 음악','contemporary Christian music, uplifting and worshipful vocal delivery, acoustic piano, soaring strings, warm spiritual atmosphere','contemporary Christian worship instrumental, warm piano, soaring strings, hopeful spiritual ambience'],
            ['gospel','찬송가/가스펠','heartfelt gospel hymn, soulful and inspiring vocal harmonies, warm piano and organ accompaniment','inspiring gospel hymn instrumental, soulful piano and warm organ arrangement'],
            ['buddhist','불교음악/명상','serene meditative music, peaceful and tranquil vocal chant, meditative bells, soft bamboo flute and calm ambience','serene meditative instrumental, tranquil temple bells, bamboo flute and peaceful atmospheric soundscape'],
            ['sacred','성가/종교음악','sacred choral music, reverent and graceful vocal tone, resonant cathedral acoustics and gentle pipe organ','reverent sacred instrumental, cathedral acoustics, gentle organ and peaceful strings'],
            ['acoustic','어쿠스틱/인디','acoustic indie, intimate and raw indie vocal tone, natural and warm acoustic vibe','warm acoustic indie instrumental, natural acoustic guitar and intimate arrangement'],
            ['rnb','힙합/알앤비','hip-hop and R&B, smooth and soulful R&B rhythm, rhythmic and groovy vocal delivery','hip-hop and R&B instrumental, soulful chords, smooth bass and groovy beats'],
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
        mood:{label:'감정선 및 무드',musicOnly:true,items:[
            ['sad','애절함/슬픔','sorrowful and tearful singing voice, full of melancholy and deep emotion','sorrowful instrumental mood, melancholy melodies and deep emotion'],
            ['joyful','밝고 신남','joyful and smiling vocal tone, full of happiness and bright energy','joyful instrumental mood, cheerful melodies and bright energy'],
            ['dreamy','몽환적/신비로움','dreamy and ethereal vocal with a soft reverb-like quality, mysterious tone','dreamy and ethereal instrumental textures, spacious reverb and a mysterious mood'],
            ['passionate','열정적/강렬함','passionate and intense vocal delivery, fierce and emotional projection','passionate instrumental mood, intense rhythms and a dramatic build'],
            ['warm','따뜻함/편안함','warm and comforting vocal delivery, gentle and reassuring emotion','warm and comforting instrumental mood, gentle melodies and a relaxed atmosphere'],
            ['hopeful','희망/벅찬 감동','hopeful and uplifting vocals, a growing sense of wonder and inspiration','hopeful uplifting instrumental mood, a growing sense of wonder and inspiration'],
            ['calm','차분함/집중','calm and restrained vocals, peaceful and unhurried emotion','calm and peaceful instrumental mood, restrained melodies suitable for focus']
        ]},
        tempo:{label:'템포',musicOnly:true,items:[
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
        ]},
        sfxVideo:{label:'영상 편집 효과음 (시간 자동 설정)',sfxOnly:true,items:[
            ['whoosh','화면 전환 슉 (2초)','fast cinematic whoosh swoosh sound effect, clean air transition, swift camera pan movement',2],
            ['pop','자막 팝업 뿅 (2초)','cute cartoon pop bubble sound effect, clean wooden plop, cheerful bright UI notification',2],
            ['impact','화면 강조 쿵 (3초)','powerful cinematic hit impact boom sound effect, deep bass resonance, dramatic sub drop punch',3],
            ['click','마우스 클릭 (2초)','clean mechanical mouse click and digital tap sound effect, crisp modern UI interaction',2],
            ['camera','카메라 셔터 (2초)','vintage mechanical SLR camera shutter click and flash sound effect, crisp snapshot foley',2],
            ['ding','정답·알림 띵동 (3초)','bright cheerful success chime bell ding sound effect, clean correct answer quiz notification',3],
            ['buzzer','오답 삐익 (2초)','game show wrong answer buzzer sound effect, comical error fail beep, distinct punchy tone',2],
            ['typing','키보드 타자음 (6초)','fast rhythmic mechanical keyboard typing sound effect, crisp key clacks, steady typing pace',6],
            ['paper','종이 넘김 (2초)','crisp book page turn, clean paper flip rustle sound effect, realistic foley',2],
            ['scratch','레코드 스크래치·반전 (2초)','vinyl record scratch needle stop sound effect, comical sudden stop and record pause',2],
            ['riser','긴장감 고조 라이저 (5초)','cinematic tension riser sound effect, suspenseful rising swell building up to climax',5],
            ['applause','환호와 박수 (6초)','enthusiastic audience applause and cheering, warm crowd clapping reaction',6]
        ]},
        sfxCategory:{label:'일반 효과음 종류',sfxOnly:true,items:[
            ['nature','자연/날씨 환경음','natural weather and outdoor ambience, organic rain, wind and nature soundscape'],
            ['foley','일상/실내 폴리 효과음','crisp everyday foley sound effect, close-up object interaction and realistic texture'],
            ['footsteps','발자국/움직임 소리','clear footsteps and movement foley, realistic surface contact sound'],
            ['ui','UI/알림/버튼음','clean modern UI sound effect, crisp digital notification and button click'],
            ['impact','타격/충돌/시네마틱 임팩트','cinematic impact and boom sound effect, powerful transient and deep resonance'],
            ['scifi','SF/사이버/기계음','sci-fi futuristic mechanical and energy sound effect, clean synthetic texture'],
            ['horror','미스터리/긴장감 효과음','eerie suspense sound effect, unsettling texture and dark tension']
        ]},
        sfxSpace:{label:'공간감 및 녹음 질감',sfxOnly:true,items:[
            ['dry','가깝고 선명하게 (무향/클로즈업)','close-mic dry recording, crisp transient, minimal room reverb'],
            ['room','자연스러운 실내 공간','natural indoor room acoustics, warm subtle reflections'],
            ['hall','넓고 울림 있는 공간','spacious reverberant hall and wide stereo ambience'],
            ['outdoor','탁 트인 야외 공간','open outdoor field recording perspective, natural air']
        ]}
    };
    const input=document.getElementById('prompt');
    const fields=document.getElementById('preset-fields');
    const status=document.getElementById('preset-status');
    const selected=Object.fromEntries(Object.keys(data).map(key=>[key,'']));
    let currentMode='bgm',appliedBlock='',appliedTitle='';
    const titleInput=document.getElementById('track-title');
    if(titleInput){
        titleInput.addEventListener('input',()=>{
            if(titleInput.value.trim()!==appliedTitle)appliedTitle='';
        });
    }
    function determineSfxTitle(){
        if(currentMode!=='sfx')return '';
        if(selected.sfxVideo){
            const match=data.sfxVideo.items.find(item=>item[0]===selected.sfxVideo);
            if(match)return match[1].replace(/\s*\(\d+초\)/,'').trim();
        }
        if(selected.sfxCategory){
            const match=data.sfxCategory.items.find(item=>item[0]===selected.sfxCategory);
            if(match)return match[1].trim();
        }
        return '';
    }
    function syncSfxTitle(){
        if(currentMode!=='sfx')return;
        const titleEl=document.getElementById('track-title');
        if(!titleEl)return;
        const newTitle=determineSfxTitle();
        if(!titleEl.value.trim()||titleEl.value.trim()===appliedTitle){
            titleEl.value=newTitle;
            appliedTitle=newTitle;
            titleEl.dispatchEvent(new Event('input',{bubbles:true}));
        }
    }
    function applyDuration(sec){
        if(!sec)return;
        const slider=document.getElementById('seconds');
        const numberInput=document.getElementById('seconds-number');
        if(!slider)return;
        const minSec=Number(slider.min)||1;
        const maxSec=Number(slider.max)||120;
        const clamped=Math.max(minSec,Math.min(maxSec,sec));
        slider.value=clamped;
        if(numberInput)numberInput.value=clamped;
        slider.dispatchEvent(new Event('input',{bubbles:true}));
    }
    for(const [key,group] of Object.entries(data)){
        const field=document.createElement('div');field.className='preset-field';field.dataset.presetGroup=key;
        const label=document.createElement('label');label.htmlFor='preset-'+key;label.textContent=group.label;
        const select=document.createElement('select');select.id='preset-'+key;
        select.add(new Option('선택 안 함',''));
        group.items.forEach(([value,name])=>select.add(new Option(name,value)));
        select.onchange=()=>{
            const old=selected[key];selected[key]=select.value;
            if(!compose()){selected[key]=old;select.value=old;}
            else{
                if(select.value&&group.items){
                    const match=group.items.find(item=>item[0]===select.value);
                    if(match&&typeof match[3]==='number')applyDuration(match[3]);
                }
                syncSfxTitle();
            }
        };
        field.append(label,select);fields.append(field);
    }
    function phrases(){
        const result=[];
        for(const [key,group] of Object.entries(data)){
            if(group.vocalOnly&&currentMode!=='song')continue;
            if(group.musicOnly&&currentMode==='sfx')continue;
            if(group.sfxOnly&&currentMode!=='sfx')continue;
            const item=group.items.find(item=>item[0]===selected[key]);
            if(item){
                const text=group.sfxOnly?item[2]:(currentMode==='song'?item[2]:(item[3]||item[2]));
                result.push(text);
            }
        }
        if(result.length&&currentMode==='bgm')result.push('instrumental, no vocals');
        if(result.length&&currentMode==='sfx')result.push('high quality sound effect, no music, no vocals');
        return result;
    }
    function refreshFields(){
        for(const [key,group] of Object.entries(data)){
            const select=document.getElementById('preset-'+key);
            select.value=selected[key];
            const hidden=(group.vocalOnly&&currentMode!=='song')||(group.musicOnly&&currentMode==='sfx')||(group.sfxOnly&&currentMode!=='sfx');
            select.parentElement.hidden=hidden;select.disabled=hidden;
        }
        const shortcuts=currentMode==='sfx'
            ?[['whoosh','화면전환 슉 (2초)'],['pop','자막 팝업 (2초)'],['impact','화면 강조 (3초)']]
            :[['lofi','로파이'],['ambient','앰비언트'],['acoustic','어쿠스틱/인디']];
        const shortcutKey=currentMode==='sfx'?'sfxVideo':'genre';
        document.querySelectorAll('[data-preset-genre]').forEach((button,index)=>{
            const [val,label]=shortcuts[index]||shortcuts[0];
            button.dataset.presetGenre=val;button.textContent=label;
            button.setAttribute('aria-pressed',String(selected[shortcutKey]===val));
        });
        const summary=document.querySelector('.prompt-presets>summary');
        if(summary)summary.textContent=currentMode==='sfx'?'효과음 스타일 프리셋':'음악 스타일 프리셋';
        if(currentMode==='sfx'){
            const details=document.querySelector('.prompt-presets');
            if(details)details.open=true;
        }
        document.getElementById('preset-mode-help').textContent=currentMode==='song'
            ?'항목별로 하나씩 조합하세요. 템포와 창법은 함께 선택할 수 있습니다.'
            :currentMode==='sfx'
            ?'영상 편집 효과음 프리셋을 선택하면 최적의 생성 시간이 자동으로 설정됩니다.'
            :'배경음악에서는 보컬 음색과 창법을 제외한 연주용 표현을 입력합니다.';
    }
    function updateStatus(message='',isError=false){
        const max=2000;
        let note='';
        if(currentMode==='sfx'&&selected.sfxVideo){
            const match=data.sfxVideo.items.find(item=>item[0]===selected.sfxVideo);
            if(match&&typeof match[3]==='number')note=` · ${match[1]} (${match[3]}초 자동 설정)`;
        }
        status.textContent=message||(`설명 ${input.value.length} / ${max}자 · 직접 쓴 설명도 유지됩니다.`+note);
        status.classList.toggle('preset-error',input.value.length>max||isError);
    }
    function compose(allowOverLimit=false){
        const base=appliedBlock&&input.value.includes(appliedBlock)?input.value.replace(appliedBlock,''):input.value;
        const parts=phrases();
        const block=parts.length?(base.length?'\n\n':'')+'Style: '+parts.join('; ')+'.':'';
        const value=base+block,max=2000;
        if(value.length>max&&!allowOverLimit){
            updateStatus(`설명이 ${max}자를 넘게 됩니다. 직접 입력한 설명을 줄인 뒤 다시 선택해 주세요.`,true);
            return false;
        }
        input.value=value;appliedBlock=block;refreshFields();updateStatus();input.dispatchEvent(new Event('input',{bubbles:true}));return true;
    }
    input.addEventListener('input',()=>{
        if(appliedBlock&&!input.value.includes(appliedBlock)){
            appliedBlock='';Object.keys(selected).forEach(key=>selected[key]='');refreshFields();
            updateStatus('수정한 문구는 직접 쓴 설명으로 유지합니다. 프리셋을 새로 조합할 수 있습니다.');
        }else updateStatus();
    });
    document.querySelectorAll('[data-preset-genre]').forEach(button=>button.onclick=()=>{
        const key=currentMode==='sfx'?'sfxVideo':'genre';
        const old=selected[key];selected[key]=old===button.dataset.presetGenre?'':button.dataset.presetGenre;
        if(!compose()){selected[key]=old;refreshFields();}
        else{
            if(selected[key]&&data[key]?.items){
                const match=data[key].items.find(item=>item[0]===selected[key]);
                if(match&&typeof match[3]==='number')applyDuration(match[3]);
            }
            syncSfxTitle();
        }
    });
    document.getElementById('clear-presets').onclick=()=>{
        Object.keys(selected).forEach(key=>selected[key]='');compose(true);syncSfxTitle();
    };
    window.MusicPresets={
        snapshot(){return {selected:{...selected},appliedBlock,currentMode,appliedTitle};},
        restore(saved,mode){
            Object.keys(selected).forEach(key=>selected[key]=saved?.selected?.[key]||'');
            appliedBlock=saved?.appliedBlock||'';currentMode=saved?.currentMode||mode;
            appliedTitle=saved?.appliedTitle||'';
            refreshFields();updateStatus();
        },
        setMode(mode){
            if(mode===currentMode)return;
            currentMode=mode;
            if(currentMode==='sfx'){
                const details=document.querySelector('.prompt-presets');
                if(details)details.open=true;
            }
            compose(true);
        },
        reset(){appliedBlock='';appliedTitle='';Object.keys(selected).forEach(key=>selected[key]='');refreshFields();updateStatus();syncSfxTitle();}
    };
    refreshFields();updateStatus();
})();
