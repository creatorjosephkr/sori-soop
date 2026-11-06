/* Download only after the user chooses a feature; prompts are never uploaded. */
(()=>{
    const panel=document.getElementById('model-setup'),message=document.getElementById('setup-status');
    const labels={bgm:'배경음악',translation:'한국어 번역',song:'노래'};
    let running=false;
    async function update(){
        try{
            const status=await api('/api/setup');
            panel.hidden=Object.values(status.ready).every(Boolean)&&!status.active&&status.state==='idle';
            for(const button of panel.querySelectorAll('[data-setup]')){
                const kind=button.dataset.setup,ready=status.ready[kind];
                button.disabled=status.active||activeJob||ready;
                button.textContent=labels[kind]+(ready?' 준비 완료':' 준비');
            }
            message.textContent=status.active?labels[status.component]+' 모델을 준비하고 있습니다. 첫 준비는 인터넷 속도에 따라 수 분 이상 걸릴 수 있습니다.':status.error||(status.state==='completed'?'준비를 마쳤습니다. 원하는 기능으로 음악을 만들어 보세요.':'');
            if(running&&!status.active){await refresh();await jobs();}
            running=status.active;
        }catch(error){message.textContent=error.message;}
        if(running)setTimeout(update,2000);
    }
    panel.addEventListener('click',async event=>{
        const button=event.target.closest('[data-setup]');if(!button||button.disabled)return;
        panel.querySelectorAll('button').forEach(item=>item.disabled=true);
        try{await api('/api/setup',{component:button.dataset.setup});running=true;}
        catch(error){await update();message.textContent=error.message;return;}
        update();
    });
    update();
})();
