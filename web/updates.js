/* Update checks contain no prompts, lyrics, audio, or device details. */
(()=>{
    const button=document.getElementById('check-updates');
    const status=document.getElementById('update-check-status');
    const dialog=document.getElementById('update-dialog');
    const titleEl=document.getElementById('update-title');
    const descEl=document.getElementById('update-description');
    const guidanceEl=document.getElementById('update-guidance');
    const downloadBtn=document.getElementById('update-download');
    const releaseBtn=document.getElementById('update-release');
    const laterBtn=document.getElementById('update-later');
    const openStatusEl=document.getElementById('update-open-status');
    let pending=null,manualPending=false,opener=null,checking=false;

    function openDialog(){
        if(!dialog.open){
            opener=document.activeElement;
            dialog.showModal();
        }
    }

    function renderDialogState(mode,data){
        if(openStatusEl)openStatusEl.textContent='';
        if(mode==='checking'){
            if(titleEl)titleEl.textContent='업데이트 확인';
            if(descEl)descEl.textContent='새 버전을 확인하고 있습니다…';
            if(guidanceEl)guidanceEl.hidden=true;
            if(downloadBtn)downloadBtn.hidden=true;
            if(releaseBtn)releaseBtn.hidden=false;
            if(laterBtn)laterBtn.textContent='닫기';
            return;
        }
        if(mode==='available'){
            if(titleEl)titleEl.textContent='새로운 소리숲이 준비됐어요';
            if(descEl)descEl.textContent=`현재 v${data.currentVersion} → 새 버전 v${data.latestVersion}`;
            if(guidanceEl)guidanceEl.hidden=false;
            if(downloadBtn)downloadBtn.hidden=!data.releaseUrl;
            if(releaseBtn)releaseBtn.hidden=false;
            if(laterBtn)laterBtn.textContent='나중에';
            return;
        }
        if(mode==='latest'){
            if(titleEl)titleEl.textContent='최신 버전입니다';
            if(descEl)descEl.textContent=`현재 최신 버전(v${data.currentVersion})을 사용하고 있습니다.`;
            if(guidanceEl)guidanceEl.hidden=true;
            if(downloadBtn)downloadBtn.hidden=true;
            if(releaseBtn)releaseBtn.hidden=false;
            if(laterBtn)laterBtn.textContent='확인';
            return;
        }
        if(mode==='error'){
            if(titleEl)titleEl.textContent='업데이트 확인 실패';
            if(descEl)descEl.textContent=data?.message||'업데이트 정보를 확인할 수 없습니다.';
            if(guidanceEl)guidanceEl.hidden=true;
            if(downloadBtn)downloadBtn.hidden=true;
            if(releaseBtn)releaseBtn.hidden=false;
            if(laterBtn)laterBtn.textContent='확인';
        }
    }

    function present(){
        if(!pending||document.querySelector('dialog[open]'))return;
        if(!manualPending&&document.getElementById('model-setup')?.getAttribute('aria-busy')==='true')return;
        // Keep startup notices out of an active generation workflow.
        if(!manualPending&&typeof jobHistory!=='undefined'&&jobHistory.some(j=>['queued','running'].includes(j.status)))return;
        renderDialogState('available',pending);
        pending=null;manualPending=false;
        openDialog();
    }

    async function check(manual){
        if(checking)return;
        checking=true;button.disabled=true;
        if(manual){
            if(status)status.textContent='';
            renderDialogState('checking');
            openDialog();
        }
        try{
            const result=await api('/api/updates/check',{});
            if(manual){
                renderDialogState(result.available?'available':'latest',result);
                openDialog();
            }else if(result.available){
                pending=result;manualPending=false;present();
            }
        }catch(error){
            if(manual){
                renderDialogState('error',error);
                openDialog();
            }
        }
        finally{checking=false;button.disabled=false;}
    }

    button.onclick=()=>check(true);
    laterBtn.onclick=()=>dialog.close();
    document.getElementById('close-update-dialog')?.addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>opener?.focus({preventScroll:true}));
    dialog.addEventListener('click',event=>{
        const box=dialog.getBoundingClientRect();
        if(event.target===dialog&&(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom))dialog.close();
    });
    downloadBtn.onclick=async()=>{
        downloadBtn.disabled=true;
        openStatusEl.textContent='최신 릴리즈 페이지를 기본 웹브라우저에서 열고 앱을 종료합니다…';
        try{await api('/api/updates/open/download',{});}
        catch(error){openStatusEl.textContent=error.message;downloadBtn.disabled=false;}
    };
    releaseBtn.onclick=async()=>{
        releaseBtn.disabled=true;
        try{await api('/api/updates/open/release',{});openStatusEl.textContent='기본 웹브라우저에서 열었습니다.';}
        catch(error){openStatusEl.textContent=error.message;}
        finally{releaseBtn.disabled=false;}
    };
    setTimeout(()=>check(false),1500);
    setInterval(present,2000);
})();
