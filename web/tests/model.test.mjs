import test from "node:test";
import assert from "node:assert/strict";
import {CONFIG,calculateDose,correctedNullTi,postContrastT1,signalAtTi,simulate,virtualLesionNullTi,bloodConcentrationFromDoses,bloodConcentration,bloodNullTiFromT1,bloodSignalAtTi,bloodSignalCurve} from "../model.js";
const close=(a,e,t)=>assert.ok(Math.abs(a-e)<=t,`${a} != ${e}`);
test("代表体重の投与量がPython版と一致する",()=>{for(const[w,f,s,total]of[[30,1.5,4.5,6],[45,2.3,6.7,9],[50,2.5,7.5,10],[55,2.8,7.2,10],[70,3.5,6.5,10],[100,5,5,10]]){const d=calculateDose(w);close(d.firstVolumeMl,f,1e-9);close(d.secondVolumeMl,s,1e-9);close(d.totalVolumeMl,total,1e-9);}});
test("2回目注入は1回目注入開始の1分後",()=>close(CONFIG.secondInjectionTime,1,1e-12));
test("標準入力の結果",()=>{const r=simulate({weight:50,scoutAfterSecond:5,psirAfterSecond:8,nativeT1:1250,nativeBloodT1:1800});close(r.myocardialNullTi,245.67326044684654,1e-9);close(r.bloodNullTi,148.0759105848951,1e-9);close(r.psirNullTi,270.8916283609578,1e-9);});
test("45 kgは0.200 mmol/kg",()=>close(calculateDose(45).totalDoseMmolPerKg,.2,1e-12));
test("nullで信号ゼロ",()=>close(signalAtTi(250,250),0,1e-12));
test("T1とnull式",()=>{const t=postContrastT1(1250,.5,5);close(correctedNullTi(t,57),t*Math.log(2)+57,1e-12);});
test("PSIRはscout以後",()=>assert.throws(()=>simulate({weight:50,scoutAfterSecond:8,psirAfterSecond:5,nativeT1:1250,nativeBloodT1:1800}),/TI scout/));
test("仮想病変null TIは正常心筋より50 ms早い",()=>close(virtualLesionNullTi(247),197,1e-12));
test("仮想病変は自身のnull TIで信号ゼロ",()=>{const lesionNull=virtualLesionNullTi(247);close(signalAtTi(lesionNull,lesionNull),0,1e-12);});
test("正常心筋null TIでは仮想病変が正常心筋より高信号",()=>{const normalNull=247,lesionNull=virtualLesionNullTi(normalNull);assert.ok(signalAtTi(lesionNull,normalNull)>signalAtTi(normalNull,normalNull));});

const standard={weight:50,scoutAfterSecond:5,psirAfterSecond:8,nativeT1:1250,nativeBloodT1:1800};
test("Ohta条件の4点近似とR²（提示されたER後平均値）",()=>{
  const times=[2,5,9,15],observed=[.545,.422,.330,.262],expected=[.528,.441,.346,.241];
  const predicted=times.map(t=>bloodConcentrationFromDoses(.05,.05,t,100/60).total);
  predicted.forEach((v,i)=>close(v,expected[i],.0005));
  const mean=observed.reduce((a,b)=>a+b,0)/4;
  const r2=1-predicted.reduce((s,v,i)=>s+(v-observed[i])**2,0)/observed.reduce((s,v)=>s+(v-mean)**2,0);
  close(r2,.9703562067597021,1e-10);
});
test("2回目投与前は第2項ゼロ、開始時に加算",()=>{
  const tau=100/60;
  const before=bloodConcentrationFromDoses(.05,.05,tau-.001,tau);
  assert.equal(before.second,0);close(before.total,5.657*.05*Math.exp(-.06020*(tau-.001)),1e-12);
  close(bloodConcentrationFromDoses(.05,.05,tau,tau).second,5.657*.05,1e-12);
});
test("血液T1の秒/ms換算とnull・Magnitude信号",()=>{
  const t1=postContrastT1(1800,.5,5);
  close(t1,1000/(1/1.8+2.5),1e-12);
  const nullTi=bloodNullTiFromT1(t1);close(nullTi,t1*Math.log(2),1e-12);
  close(bloodSignalAtTi(t1,nullTi),0,1e-12);close(bloodSignalAtTi(t1,0),100,1e-12);
  close(bloodSignalAtTi(t1,300),100*Math.abs(1-2*Math.exp(-300/t1)),1e-12);
  const curve=bloodSignalCurve(t1);assert.equal(curve.ti.length,701);assert.ok(curve.signal.every(s=>s>=0&&s<=100));
  curve.signal.forEach((s,i)=>close(s,signalAtTi(nullTi,i),1e-10));
});
test("心筋係数・校正は血液へ影響せず、血液係数も心筋へ影響しない",()=>{
  const base=simulate(standard);
  const myoChanged=simulate({...standard,settings:{aPk:8,washout:.1,facilityOffset:100}});
  close(myoChanged.bloodNullTi,base.bloodNullTi,1e-12);assert.notEqual(myoChanged.myocardialNullTi,base.myocardialNullTi);
  const bloodChanged=simulate({...standard,settings:{aBlood:8,bloodWashout:.1}});
  close(bloodChanged.myocardialNullTi,base.myocardialNullTi,1e-12);close(bloodChanged.psirNullTi,base.psirNullTi,1e-12);
  assert.notEqual(bloodChanged.bloodNullTi,base.bloodNullTi);
  assert.notEqual(base.myocardialNullTi-base.bloodNullTi,myoChanged.myocardialNullTi-myoChanged.bloodNullTi);
});
test("施設投与量と1分の間隔をそのまま血液へ使用",()=>{
  for(const weight of [30,45,50,70,100]){
    const d=calculateDose(weight),actual=bloodConcentration(weight,6);
    const expected=bloodConcentrationFromDoses(d.firstDoseMmolPerKg,d.secondDoseMmolPerKg,6,1);
    assert.deepEqual(actual,expected);
  }
});
