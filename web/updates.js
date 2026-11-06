/* Update checks contain no prompts, lyrics, audio, or device details. */
(()=>{
    const button=document.getElementById('check-updates');
    const status=document.getElementById('update-check-status');
    const dialog=document.getElementById('update-dialog');
    let pending=null,manualPending=false,opener=null,checking=false;
    function present(){
        if(!pending||document.querySelector('dialog[open]'))return;
        // Keep startup notices out of an active generation workflow.
        if(!manualPending&&typeof jobHistory!=='undefined'&&jobHistory.some(j=>['queued','running'].includes(j.status)))return;
        opener=document.activeElement;
        document.getElementById('update-description').textContent=`현재 v${pending.currentVersion} → 새 버전 v${pending.latestVersion}`;
        document.getElementById('update-download').hidden=!pending.downloadUrl;
        document.getElementById('update-open-status').textContent='';
        pending=null;manualPending=false;dialog.showModal();
    }
    async function check(manual){
        if(checking)return;
        checking=true;button.disabled=true;
        if(manual)status.textContent='새 버전을 확인하고 있습니다…';
        try{
            const result=await api('/api/updates/check',{});
            status.textContent=manual?(result.available?'새 버전이 있습니다.':`최신 버전(v${result.currentVersion})을 사용하고 있습니다.`):'';
            if(result.available){pending=result;manualPending=manual;present();}
        }catch(error){if(manual)status.textContent=error.message;}
        finally{checking=false;button.disabled=false;}
    }
    button.onclick=()=>check(true);
    document.getElementById('update-later').onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>opener?.focus({preventScroll:true}));
    dialog.addEventListener('click',event=>{
        const box=dialog.getBoundingClientRect();
        if(event.target===dialog&&(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom))dialog.close();
    });
    for(const [id,target] of [['update-download','download'],['update-release','release']]){
        document.getElementById(id).onclick=async()=>{
            const control=document.getElementById(id),message=document.getElementById('update-open-status');
            control.disabled=true;
            try{await api('/api/updates/open/'+target,{});message.textContent='기본 웹브라우저에서 열었습니다.';}
            catch(error){message.textContent=error.message;}
            finally{control.disabled=false;}
        };
    }
    setTimeout(()=>check(false),1500);
    setInterval(present,2000);
})();
