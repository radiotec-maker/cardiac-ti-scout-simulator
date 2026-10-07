import{CONFIG,grayscale,signalAtTi,signalCurve,bloodSignalAtTi,bloodSignalCurve,simulate,myocardialConcentration,postContrastT1,correctedNullTi,virtualLesionNullTi}from"./model.js";

const $=id=>document.getElementById(id);
// LGEの位置・分布は、Shah DJらの虚血性／非虚血性パターン分類と、
// 後藤・佐久間「MRIによる心筋疾患の診断」図1を参考に独自に模式化している。
// 原図・臨床画像そのものは転載しない。
const LESION_PRESETS={
  myocarditis:{
    name:"心筋炎",
    description:"非虚血性・心外膜側型：下壁から側壁の心外膜側に分布する代表的なLGEパターンです。"
  },
  hcm:{
    name:"HCM",
    description:"非虚血性・心筋中層型：前後の右室接合部に限局する斑状LGEとして表示します。"
  },
  dcm:{
    name:"DCM",
    description:"非虚血性・心筋中層型：心室中隔の心筋中層にみられる線状LGEです。"
  },
  amyloidosis:{
    name:"心アミロイドーシス",
    description:"非虚血性・びまん性心内膜下型：全周に及びながら、分布の厚さが不均一なLGEとして表示します。"
  },
  fabry:{
    name:"Fabry病",
    description:"非虚血性・心筋中層型：典型的な心基部下側壁の限局性LGEとして表示します。"
  },
  sarcoidosis:{
    name:"心サルコイドーシス",
    description:"非虚血性・心外膜側型：心内膜を避け、心外膜側に分布するLGEとして表示します。"
  },
  "infarct-subendocardial":{
    name:"心筋梗塞（心内膜下型）",
    description:"虚血性・心内膜下型：冠動脈支配領域に一致し、心内膜下を含むLGEとして表示します。"
  },
  "infarct-transmural":{
    name:"心筋梗塞（貫壁型）",
    description:"虚血性・貫壁型：心内膜下から心外膜側まで壁全層へ及ぶLGEとして表示します。"
  }
};

const state={displayTi:CONFIG.ti.default,result:null,lesionEnabled:false,lesionPattern:"myocarditis"};
const inputs={weight:$("weight"),scoutAfterSecond:$("scout-time"),psirAfterSecond:$("psir-time"),nativeT1:$("native-t1"),nativeBloodT1:$("native-blood-t1")};
const fmt=(v,d=0)=>Number(v).toFixed(d),signed=v=>`${v>=0?"+":""}${fmt(v)} ms`;
function readInput(){return Object.fromEntries(Object.entries(inputs).map(([k,i])=>[k,Number(i.value)]));}
function currentPreset(){return LESION_PRESETS[state.lesionPattern];}
function lesionNullTi(){return virtualLesionNullTi(state.result.myocardialNullTi);}

function reset(){
  inputs.weight.value=50;inputs.scoutAfterSecond.value=5;inputs.psirAfterSecond.value=8;inputs.nativeT1.value=1250;inputs.nativeBloodT1.value=1800;
  state.displayTi=250;state.lesionEnabled=false;state.lesionPattern="myocarditis";
  $("display-ti").value=250;$("lesion-pattern").value=state.lesionPattern;syncLesionControls();update();
}

function syncLesionControls(){
  const preset=currentPreset(),button=$("toggle-lesion"),controls=$("lesion-controls");
  button.setAttribute("aria-pressed",String(state.lesionEnabled));
  button.textContent=state.lesionEnabled?"病変を削除":"＋ 仮想病変を追加";
  controls.hidden=!state.lesionEnabled;
  $("lesion-description").textContent=preset.description;
  $("illustration-lesion-label").hidden=!state.lesionEnabled;
  $("illustration-lesion-label").textContent=state.lesionEnabled?`仮想LGE：${preset.name}`:"";
}

function renderDose(r){
  const d=r.dose;$("dose-caption").textContent=`設定体重 ${fmt(r.weight)} kg に対するインジェクター設定値です。`;
  $("first-volume").textContent=`${fmt(d.firstVolumeMl,1)} mL`;$("second-volume").textContent=`${fmt(d.secondVolumeMl,1)} mL`;$("total-dose").textContent=`${fmt(d.totalDoseMmolPerKg,3)} mmol/kg`;
  const shortfall=Math.max(0,.2-d.totalDoseMmolPerKg);
  $("dose-details").innerHTML=`<table><tr><th>項目</th><th>1回目</th><th>2回目</th></tr><tr><td>投与量</td><td>${fmt(d.firstVolumeMl,1)} mL</td><td>${fmt(d.secondVolumeMl,1)} mL</td></tr><tr><td>実投与量</td><td>${fmt(d.firstDoseMmolPerKg,3)}</td><td>${fmt(d.secondDoseMmolPerKg,3)} mmol/kg</td></tr><tr><td>注入時間</td><td>${fmt(d.firstInjectionDurationS,2)} s</td><td>${fmt(d.secondInjectionDurationS,2)} s</td></tr></table><p>${shortfall?`目標を ${fmt(shortfall,3)} mmol/kg下回ります。`:"目標0.200 mmol/kgを満たします。"}</p>`;
}

function renderPrimary(r){
  $("result-caption").textContent=`設定体重 ${fmt(r.weight)} kgで計算した推定値です。`;
  $("primary-results").innerHTML=`<div class="result-block"><span class="label">TI scout ${fmt(r.scoutAfterSecond,1)}分後の予想心筋null TI</span><strong class="value">${fmt(r.myocardialNullTi)} ms</strong></div><div class="result-block"><span class="label">TI scout ${fmt(r.scoutAfterSecond,1)}分後の予想血液null TI</span><strong class="value">${fmt(r.bloodNullTi)} ms</strong></div><div class="result-block"><span class="label">PSIR ${fmt(r.psirAfterSecond,1)}分後の予想心筋null TI</span><strong class="value">${fmt(r.psirNullTi)} ms</strong><div class="difference">TI scout正常心筋null TIとの差<br>${signed(r.psirVsScoutMyo)}</div><div class="difference">TI scout血液null TIとの差<br>${signed(r.psirVsScoutBlood)}<small>（TI scout正常心筋との差：${signed(r.scoutMyoVsBlood)}）</small></div></div>`;
}

function point(cx,cy,rx,ry,degrees){const radians=degrees*Math.PI/180;return{x:cx+rx*Math.cos(radians),y:cy+ry*Math.sin(radians)};}
function annularSectorPath(innerRx,innerRy,outerRx,outerRy,start,end){
  const cx=238,cy=120,outerStart=point(cx,cy,outerRx,outerRy,start),outerEnd=point(cx,cy,outerRx,outerRy,end),innerEnd=point(cx,cy,innerRx,innerRy,end),innerStart=point(cx,cy,innerRx,innerRy,start),large=Math.abs(end-start)>180?1:0;
  return`M ${outerStart.x} ${outerStart.y} A ${outerRx} ${outerRy} 0 ${large} 1 ${outerEnd.x} ${outerEnd.y} L ${innerEnd.x} ${innerEnd.y} A ${innerRx} ${innerRy} 0 ${large} 0 ${innerStart.x} ${innerStart.y} Z`;
}
function ellipsePath(cx,cy,rx,ry){
  return`M ${cx-rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx+rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx-rx} ${cy} Z`;
}
function lesionPath(pattern){
  // 座標は本アプリの左室短軸模式図専用。角度はSVG座標系で定義する。
  if(pattern==="myocarditis")return annularSectorPath(76,78,92,94,55,145);
  // HCM：前後の右室接合部だけに、連続しない斑状病変を置く。
  if(pattern==="hcm")return `${ellipsePath(181,55,10,7)} ${ellipsePath(179,184,11,7)}`;
  // DCM：心室中隔中層に沿う、細い線状病変として表示する。
  if(pattern==="dcm")return annularSectorPath(69,72,75,78,143,217);
  // アミロイドーシス：全周性だが、部位ごとに厚さが異なる不整な心内膜下病変。
  if(pattern==="amyloidosis")return `${annularSectorPath(50,53,67,70,0,72)} ${annularSectorPath(52,55,74,77,70,137)} ${annularSectorPath(49,52,69,72,135,202)} ${annularSectorPath(54,57,77,80,200,267)} ${annularSectorPath(50,53,71,74,265,327)} ${annularSectorPath(53,56,78,81,325,360)}`;
  // Fabry病：心基部下側壁の心筋中層にみられる限局性病変。
  if(pattern==="fabry")return annularSectorPath(64,67,79,82,38,92);
  if(pattern==="sarcoidosis")return `${annularSectorPath(76,78,92,94,18,60)} ${annularSectorPath(76,78,92,94,158,198)}`;
  if(pattern==="infarct-transmural")return annularSectorPath(50,53,92,94,35,108);
  return annularSectorPath(50,53,72,75,35,108);
}
function heartSvg(myoSignal,bloodSignal,lesionSignal=null){
  const m=grayscale(myoSignal,.5),b=grayscale(bloodSignal),lesion=lesionSignal===null?"":`<path class="lesion-outline lesion-${state.lesionPattern}" d="${lesionPath(state.lesionPattern)}" fill="rgb(${grayscale(lesionSignal,.5)},${grayscale(lesionSignal,.5)},${grayscale(lesionSignal,.5)})"/>`;
  return`<svg viewBox="0 0 360 240" role="img" aria-label="左室・右室短軸模式図"><path d="M196 40C105 32 45 78 55 143C63 198 123 218 190 185C166 157 161 83 196 40Z" fill="rgb(${b},${b},${b})" stroke="#555" stroke-width="3"/><ellipse cx="238" cy="120" rx="92" ry="94" fill="rgb(${m},${m},${m})" stroke="#464646" stroke-width="4"/>${lesion}<ellipse cx="238" cy="120" rx="50" ry="53" fill="rgb(${b},${b},${b})" stroke="#464646" stroke-width="3"/></svg>`;
}

function renderIllustration(){
  const r=state.result,ti=state.displayTi;$("display-ti").value=ti;$("display-ti-value").textContent=`${fmt(ti)} ms`;$("display-ti-heading").textContent=`表示TI：${fmt(ti)} ms`;
  const lesionSignal=state.lesionEnabled?signalAtTi(lesionNullTi(),ti):null;
  $("heart-illustration").innerHTML=heartSvg(signalAtTi(r.myocardialNullTi,ti),bloodSignalAtTi(r.postBloodT1,ti),lesionSignal);
  Plotly.relayout("signal-chart",{"shapes[0].x0":ti,"shapes[0].x1":ti});
}

function renderChart(r){
  const m=signalCurve(r.myocardialNullTi),b=bloodSignalCurve(r.postBloodT1);
  const traces=[{x:m.ti,y:m.signal,name:"正常心筋",mode:"lines",line:{color:"#1976b9",width:3}},{x:b.ti,y:b.signal,name:"血液",mode:"lines",line:{color:"#d33",width:3}}];
  if(state.lesionEnabled){const l=signalCurve(lesionNullTi());traces.push({x:l.ti,y:l.signal,name:`仮想LGE：${currentPreset().name}`,mode:"lines",line:{color:"#e07a16",width:4}});}
  const layout={margin:{l:58,r:20,t:45,b:125},xaxis:{title:{text:"Inversion Time（TI）［ms］",standoff:16},range:[0,700],fixedrange:true},yaxis:{title:"正規化Magnitude信号［%］",range:[0,100],fixedrange:true},hovermode:"x unified",dragmode:false,shapes:[{type:"line",x0:state.displayTi,x1:state.displayTi,y0:0,y1:1,yref:"paper",line:{color:"#333",width:2,dash:"dot"}}],legend:{orientation:"h",x:.5,xanchor:"center",y:-.38,yanchor:"top"}};
  Plotly.react("signal-chart",traces,layout,{responsive:true,displaylogo:false,scrollZoom:false,modeBarButtonsToRemove:["pan2d","zoom2d","select2d","lasso2d","zoomIn2d","zoomOut2d","autoScale2d"]});
  const chart=$("signal-chart");chart.removeAllListeners?.("plotly_click");chart.on("plotly_click",e=>{if(e.points?.length){state.displayTi=Math.round(e.points[0].x);renderIllustration();}});
}

function renderGuide(r){
  const start=r.psirAfterSecond,times=[];for(let t=start;t<=15+1e-9;t+=1)times.push(t);
  const values=times.map(t=>{const c=myocardialConcentration(r.weight,1.5+t);return correctedNullTi(postContrastT1(r.nativeT1,c.total,5),57)}),base=values[0];
  $("guide-caption").textContent=`設定体重：${fmt(r.weight)} kgで計算した推定値です。`;
  $("psir-guide").innerHTML=`<thead><tr><th>項目</th>${times.map(t=>`<th>${Number.isInteger(t)?t:fmt(t,1)}分</th>`).join("")}</tr></thead><tbody><tr><td>設定TI目安</td>${values.map(v=>`<td>${fmt(v)} ms</td>`).join("")}</tr><tr><td>${Number.isInteger(start)?start:fmt(start,1)}分からの変化</td>${values.map((v,i)=>`<td>${i===0?"±0 ms":signed(v-base)}</td>`).join("")}</tr></tbody>`;
}

function update(){try{$("error").textContent="";state.result=simulate(readInput());syncLesionControls();renderDose(state.result);renderPrimary(state.result);renderChart(state.result);renderIllustration();renderGuide(state.result);}catch(e){$("error").textContent=e.message;}}

Object.values(inputs).forEach(i=>i.addEventListener("input",update));
$("display-ti").addEventListener("input",e=>{state.displayTi=Number(e.target.value);renderIllustration();});
document.querySelectorAll("[data-shift]").forEach(b=>b.addEventListener("click",()=>{state.displayTi=Math.min(700,Math.max(0,state.displayTi+Number(b.dataset.shift)));renderIllustration();}));
$("toggle-lesion").addEventListener("click",()=>{state.lesionEnabled=!state.lesionEnabled;update();});
$("lesion-pattern").addEventListener("change",e=>{state.lesionPattern=e.target.value;update();});
$("reset").addEventListener("click",reset);
reset();
