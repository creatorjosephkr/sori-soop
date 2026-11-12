"""Exercise the ACE-Step expert settings panel in the native webview (no models required)."""
from pathlib import Path
import json, re, threading
import webview
root=Path(__file__).resolve().parent.parent
index=(root/'web/index.html').read_text(encoding='utf-8')
start=index.index('<section id="expert-settings"');end=index.index('</section>',start)+10
d0=index.index('<dialog id="expert-help-dialog"');d1=index.index('</dialog>',d0)+9
html=index[start:end]+index[d0:d1]
for name in ('icons.js','expert-settings.js'):html+='<script>'+(root/'web'/name).read_text(encoding='utf-8')+'</script>'
page=root/'build'/'expert-check.html';page.write_text('<!doctype html><meta charset=utf-8>'+html,encoding='utf-8')
window=webview.create_window('Expert checks',url=page.as_uri(),hidden=True)
result={}
def check():
 try:
  result['checks']=window.evaluate_js('''(()=>{
   localStorage.removeItem('song-expert-settings');
   const assert=(c,l)=>{if(!c)throw Error(l);};const $=id=>document.getElementById(id);const api=window.ExpertSettings;
   api.render('bgm');assert($('expert-settings').hidden,'hidden for bgm');
   api.render('song');assert(!$('expert-settings').hidden,'shown for song');
   assert($('expert-body').hidden,'collapsed by default');
   $('expert-toggle').click();assert(!$('expert-body').hidden&&$('expert-toggle').getAttribute('aria-expanded')==='true','expands');
   assert($('expert-presets').children.length===4,'4 presets');
   const helps=document.querySelectorAll('.expert-help');assert(helps.length===8,'help per item');
   assert([...helps].every(b=>b.querySelector('svg[aria-hidden=true]')&&b.getAttribute('aria-label')),'svg help buttons labelled');
   assert($('expert-reset').disabled&&$('expert-summary').textContent==='기본 · 균형','default state');
   document.querySelector('[data-preset=hifi]').click();
   assert(api.value().inferenceSteps===12&&api.value().sampler==='heun'&&$('expert-inferenceSteps').value==='12','preset applied');
   assert(!$('expert-reset').disabled&&$('expert-summary').textContent==='고음질','preset summary');
   const r=$('expert-shift');r.value='4.2';r.oninput();assert(api.value().shift===4.2&&$('expert-summary').textContent==='사용자 지정','custom edit');
   assert(JSON.parse(localStorage.getItem('song-expert-settings')).shift===4.2,'persisted');
   $('expert-reset').click();assert(JSON.stringify(api.value())===JSON.stringify(api.DEFAULTS),'reset defaults');
   helps[0].click();assert($('expert-help-dialog').open&&$('expert-help-title').textContent==='확산 단계 수'&&$('expert-help-body').textContent.length>20,'help modal');
   $('confirm-expert-help').click();assert(!$('expert-help-dialog').open,'modal closes');
   api.load({inferenceSteps:99,dcw:false});assert(api.value().inferenceSteps===8&&api.value().dcw===false,'load sanitizes');
   return 'ok';
  })()''')
 except Exception as e:result['error']=str(e)
 finally:window.destroy()
webview.start(check)
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result.get('checks')=='ok' else 1)
