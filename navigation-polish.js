;(() => {
 const nav=document.querySelector('.nav');if(!nav)return;
 let enabled=false,context=null;
 try{enabled=localStorage.getItem('sector-pulse-nav-sound')==='on';}catch{}
 const toggle=document.createElement('button');toggle.type='button';toggle.className='nav-sound-toggle';
 const render=()=>{toggle.textContent='Click sound: '+(enabled?'on':'off');toggle.setAttribute('aria-pressed',String(enabled));toggle.setAttribute('aria-label','Navigation click sound '+(enabled?'on':'off'));};render();nav.after(toggle);
 toggle.addEventListener('click',()=>{enabled=!enabled;try{localStorage.setItem('sector-pulse-nav-sound',enabled?'on':'off');}catch{}render();});
 nav.addEventListener('click',event=>{
  if(!enabled||!event.target.closest('button[data-view]'))return;
  try{const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;context=context||new Audio();context.resume().catch(()=>{});const oscillator=context.createOscillator(),gain=context.createGain(),t=context.currentTime;oscillator.type='sine';oscillator.frequency.setValueAtTime(680,t);oscillator.frequency.exponentialRampToValueAtTime(430,t+.035);gain.gain.setValueAtTime(.018,t);gain.gain.exponentialRampToValueAtTime(.0001,t+.045);oscillator.connect(gain);gain.connect(context.destination);oscillator.start(t);oscillator.stop(t+.05);}catch{}
 });
})();
