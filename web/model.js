export const CONFIG = Object.freeze({
  weight: { default: 50, min: 30, max: 100, step: 1 },
  scoutAfterSecond: { default: 5, min: 0.5, max: 13, step: 0.1 },
  psirAfterSecond: { default: 8, min: 0.5, max: 15, step: 0.1 },
  nativeT1: { default: 1250, min: 1000, max: 1600, step: 10 },
  // Existing configurable default; no supporting citation recorded in the original code/spec.
  nativeBloodT1: { default: 1800, min: 1400, max: 2200, step: 10 },
  firstDose: 0.05, targetTotalDose: 0.20, maxVolume: 10,
  injectorStep: 0.1, injectionRate: 2, secondInjectionTime: 1.0,
  aPk: 3.82385, washout: 0.054457, relaxivity: 5, facilityOffset: 57,
  // A_myo/k_myo remain aPk/washout above, independently of A_blood/k_blood.
  // Simulator-specific refit to Ohta et al. 2026 LV blood-pool T1-derived
  // apparent Gd means (2,5,9,15 min); NOT PK coefficients reported by the paper.
  aBlood: 5.657, bloodWashout: 0.06020, bloodRelaxivity: 5,
  lesionNullOffset: -50,
  ti: { default: 250, min: 0, max: 700, step: 1 },
  myocardialGamma: 0.5,
});

function finite(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${label}は有限の数値で入力してください。`);
  return number;
}
function inRange(value, minimum, maximum, label) {
  const number = finite(value, label);
  if (number < minimum || number > maximum) throw new Error(`${label}は${minimum}～${maximum}の範囲で入力してください。`);
  return number;
}

export function calculateDose(weightKg) {
  const weight = inRange(weightKg, CONFIG.weight.min, CONFIG.weight.max, "体重");
  const firstVolume = Math.ceil((CONFIG.firstDose * weight) / CONFIG.injectorStep - 1e-12) * CONFIG.injectorStep;
  const totalVolume = Math.min(CONFIG.targetTotalDose * weight, CONFIG.maxVolume);
  const secondVolume = totalVolume - firstVolume;
  if (secondVolume < -1e-12) throw new Error("2回目投与量が負になりました。");
  const totalDose = totalVolume / weight;
  return { firstVolumeMl:firstVolume, secondVolumeMl:Math.max(0,secondVolume), totalVolumeMl:totalVolume,
    firstDoseMmolPerKg:firstVolume/weight, secondDoseMmolPerKg:Math.max(0,secondVolume)/weight,
    totalDoseMmolPerKg:totalDose, targetDoseRatioPercent:totalDose/CONFIG.targetTotalDose*100,
    firstInjectionDurationS:firstVolume/CONFIG.injectionRate, secondInjectionDurationS:Math.max(0,secondVolume)/CONFIG.injectionRate };
}

function concentration(weight, timeFromFirst, amplitude, washout) {
  const dose=calculateDose(weight);
  const first=amplitude*dose.firstDoseMmolPerKg*Math.exp(-washout*timeFromFirst);
  const elapsed=timeFromFirst-CONFIG.secondInjectionTime;
  const second=elapsed<0?0:amplitude*dose.secondDoseMmolPerKg*Math.exp(-washout*elapsed);
  return {first,second,total:first+second};
}
export const myocardialConcentration=(weight,time,settings=CONFIG)=>concentration(weight,finite(time,"造影後経過時間"),settings.aPk,settings.washout);
// Dose in mmol/kg, time/tau in min, output apparent concentration in mM.
// Addition of both injections (not subtraction); the second is absent before tau.
export function bloodConcentrationFromDoses(d1,d2,time,tau,settings=CONFIG){
  const firstDose=finite(d1,"1回目投与量"),secondDose=finite(d2,"2回目投与量"),t=finite(time,"造影後経過時間"),delay=finite(tau,"注入開始間隔");
  const a=finite(settings.aBlood,"A_blood"),k=finite(settings.bloodWashout,"k_blood");
  if(firstDose<0||secondDose<0||t<0||delay<0||a<=0||k<=0)throw new Error("血液濃度計算の入力値が不正です。");
  const first=a*firstDose*Math.exp(-k*t),second=t<delay?0:a*secondDose*Math.exp(-k*(t-delay));
  return{first,second,total:first+second};
}
export function bloodConcentration(weight,time,settings=CONFIG){const d=calculateDose(weight);return bloodConcentrationFromDoses(d.firstDoseMmolPerKg,d.secondDoseMmolPerKg,time,CONFIG.secondInjectionTime,settings);}

export function postContrastT1(nativeT1Ms, concentrationMm, relaxivity, label="native T1") {
  const nativeT1=finite(nativeT1Ms,label), c=finite(concentrationMm,"見かけ濃度"), r1=finite(relaxivity,"r1");
  if(nativeT1<=0||c<0||r1<=0) throw new Error("T1計算の入力値が不正です。");
  // 1000/nativeT1Ms = native R1 in s^-1; r1 [L mmol^-1 s^-1] * c [mmol/L].
  return 1000/(1000/nativeT1+r1*c);
}
export function correctedNullTi(postT1Ms,offsetMs){const value=finite(postT1Ms,"造影後T1")*Math.log(2)+finite(offsetMs,"施設校正値");if(value<=0)throw new Error("施設校正後null TIは0より大きい必要があります。");return value;}
export function virtualLesionNullTi(normalMyocardialNullTiMs,offsetMs=CONFIG.lesionNullOffset){const normal=finite(normalMyocardialNullTiMs,"正常心筋null TI"),offset=finite(offsetMs,"病変null TI差"),value=normal+offset;if(value<=0)throw new Error("仮想病変null TIは0より大きい必要があります。");return value;}
export function signalAtTi(nullTiMs,tiMs){const nullTi=finite(nullTiMs,"null TI"),ti=inRange(tiMs,CONFIG.ti.min,CONFIG.ti.max,"表示TI");return 100*Math.abs(1-2*Math.exp(-ti/(nullTi/Math.log(2))));}
export function signalCurve(nullTiMs){const ti=[],signal=[];for(let value=0;value<=700;value+=1){ti.push(value);signal.push(signalAtTi(nullTiMs,value));}return{ti,signal};}
export function bloodNullTiFromT1(t1Ms){const t1=finite(t1Ms,"血液T1");if(t1<=0)throw new Error("血液T1は0より大きい必要があります。");return t1*Math.log(2);}
export function bloodSignalAtTi(t1Ms,tiMs){const t1=finite(t1Ms,"血液T1"),ti=inRange(tiMs,CONFIG.ti.min,CONFIG.ti.max,"表示TI");if(t1<=0)throw new Error("血液T1は0より大きい必要があります。");return 100*Math.abs(1-2*Math.exp(-ti/t1));}
export function bloodSignalCurve(t1Ms){const ti=[],signal=[];for(let value=0;value<=700;value+=1){ti.push(value);signal.push(bloodSignalAtTi(t1Ms,value));}return{ti,signal};}
export function grayscale(signalPercent,gamma=1){const signal=inRange(signalPercent,0,100,"相対信号");return Math.round(255*(signal/100)**gamma);}

export function simulate(input){
  const weight=inRange(input.weight,30,100,"体重"),scoutAfterSecond=inRange(input.scoutAfterSecond,.5,13,"TI scout撮像時刻"),psirAfterSecond=inRange(input.psirAfterSecond,.5,15,"PSIR撮像開始時刻");
  if(psirAfterSecond<scoutAfterSecond)throw new Error("PSIR撮像開始時刻はTI scout撮像時刻以上で入力してください。");
  const nativeT1=inRange(input.nativeT1,1000,1600,"正常心筋native T1"),nativeBloodT1=inRange(input.nativeBloodT1,1400,2200,"血液native T1"),settings={...CONFIG,...input.settings};
  const dose=calculateDose(weight),scoutTime=CONFIG.secondInjectionTime+scoutAfterSecond,psirTime=CONFIG.secondInjectionTime+psirAfterSecond;
  const myo=myocardialConcentration(weight,scoutTime,settings),blood=bloodConcentration(weight,scoutTime,settings),psirMyo=myocardialConcentration(weight,psirTime,settings);
  const postT1=postContrastT1(nativeT1,myo.total,settings.relaxivity),postBloodT1=postContrastT1(nativeBloodT1,blood.total,settings.bloodRelaxivity,"血液native T1"),psirPostT1=postContrastT1(nativeT1,psirMyo.total,settings.relaxivity);
  const myocardialNullTi=correctedNullTi(postT1,settings.facilityOffset),bloodNullTi=bloodNullTiFromT1(postBloodT1),psirNullTi=correctedNullTi(psirPostT1,settings.facilityOffset);
  return{weight,scoutAfterSecond,psirAfterSecond,nativeT1,nativeBloodT1,dose,myo,blood,psirMyo,postT1,postBloodT1,psirPostT1,myocardialNullTi,bloodNullTi,psirNullTi,psirVsScoutMyo:psirNullTi-myocardialNullTi,psirVsScoutBlood:psirNullTi-bloodNullTi,scoutMyoVsBlood:myocardialNullTi-bloodNullTi};
}
