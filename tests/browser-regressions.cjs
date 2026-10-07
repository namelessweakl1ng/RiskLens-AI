// UI boundary regressions use mocked responses; they never mutate stored documents.
const {chromium}=require('playwright');
const assert=require('assert/strict');
const {spawnSync}=require('child_process');
const fixture=spawnSync(process.env.PYTHON || 'python',['-c',`from tests.test_engine import engine
from backend.taxonomy import LABELS
p={label:0.08 for label in LABELS};p['high_interest']=0.28
print(engine('The parties acknowledge the signed agreement.',p).model_dump_json())`],{encoding:'utf8'});
assert.equal(fixture.status,0,fixture.stderr);
const detail=JSON.parse(fixture.stdout);
detail.filename='x'.repeat(196)+'.pdf';detail.document_id=1;
const base=process.env.RISKLENS_URL || 'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE || '/usr/bin/chromium'});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}});
  await page.route('**/documents/1',route=>route.fulfill({json:detail}));
  await page.goto(base+'/#document/1');
  await page.locator('#analysis-title').filter({hasText:detail.filename}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'long filename overflow');
  assert.match(await page.locator('#clause-rows').innerText(),/Uncertain/);
  assert.doesNotMatch(await page.locator('#clause-rows').innerText(),/Safe Clause|No finding/);
  await page.setViewportSize({width:1366,height:900});
  const pending=[];
  await page.route('**/documents?*',async route=>{
   const offset=Number(new URL(route.request().url()).searchParams.get('offset'));
   const reply=()=>route.fulfill({json:{total:60,documents:[{document_id:offset+1,filename:`document-${offset+1}`,document_type:'loan',risk_score:0,overall_risk:'Low',created_at:'2026-01-01'}]}});
   if(offset===0) await reply();else pending.push({offset,reply});
  });
  await page.getByRole('link',{name:'Document history'}).click();
  await page.locator('#history-count').filter({hasText:'1–20'}).waitFor();
  await page.locator('#history-next').click();
  await page.locator('#history-next').click();
  await page.waitForFunction(()=>true);
  const deadline=Date.now()+10000;
  while(pending.length<2 && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(pending.length,2,"both pagination requests arrived");
  await pending.find(r=>r.offset===40).reply();
  await page.locator('#history-count').filter({hasText:'41–60'}).waitFor();
  await pending.find(r=>r.offset===20).reply();
  await page.waitForTimeout(100);
  assert.match(await page.locator('#history-list').innerText(),/document-41/);
  assert.doesNotMatch(await page.locator('#history-list').innerText(),/document-21/);
  console.log('Long filename, visible uncertainty, and out-of-order pagination regressions passed.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
