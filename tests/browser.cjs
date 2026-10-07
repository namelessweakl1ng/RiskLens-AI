// Optional browser acceptance test. Use a NEW, EMPTY throwaway SQLite database.
// It creates synthetic test input, verifies real API/UI results, and deletes only its records.
const {chromium}=require('playwright');
const fs=require('fs');
const assert=require('assert/strict');
const path=require('path');
const {spawnSync}=require('child_process');
const output=process.env.BROWSER_ARTIFACTS || '/tmp/risklens-browser-artifacts';
fs.mkdirSync(output,{recursive:true});
const fixture=path.join(output,'risk-fixture.pdf');
const generated=spawnSync(process.env.PYTHON || 'python',['-c',`import pymupdf,sys
with pymupdf.open() as pdf:
 page=pdf.new_page()
 page.insert_text((40,50),'Loan agreement: borrower and lender repayment terms.\\nA processing fee of 100 rupees is payable on disbursement.\\nThe lender may repossess the collateral after default.\\nThe agreement automatically renews after twelve months.\\nThe interest rate is fixed for the entire term.')
 pdf.save(sys.argv[1])`,fixture],{encoding:'utf8'});
assert.equal(generated.status,0,generated.stderr);
const base=process.env.RISKLENS_URL || 'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE || (fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined)});
 const context=await browser.newContext({viewport:{width:1920,height:1080}});
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);
 await page.locator('#system-model').filter({hasText:'AI classifier unavailable'}).waitFor();
 await page.getByText('Your document register is empty',{exact:true}).waitFor();
 await page.screenshot({path:path.join(output,'overview-desktop.png'),fullPage:true});
 await page.locator('#file-input').setInputFiles(fixture);
 await page.getByRole('button',{name:'Analyze agreement'}).click();
 await page.locator('#analysis-title').filter({hasText:'risk-fixture.pdf'}).waitFor();
 await page.locator('#notice').filter({hasText:'Loading stored analysis'}).waitFor({state:'hidden'});
 assert.match(await page.locator('#analysis-hero').innerText(),/AI classifier unavailable/);
 assert.ok((await page.locator('#risk-cards article').count())>=3);
 await page.locator('#clause-search').fill('collateral');
 assert.equal(await page.locator('#clause-rows .clause-preview').count(),1);
 await page.locator('#clause-rows .clause-preview').click();
 assert.equal(await page.locator('#clause-rows .clause-preview').getAttribute('aria-expanded'),'true');
 assert.match(await page.locator('.expanded-row:visible').innerText(),/No model inference/);
 await page.locator('#clause-search').fill('');
 await page.locator('#severity-filter').selectOption('critical');
 assert.equal(await page.locator('#clause-rows .clause-preview').count(),1);
 await page.locator('#severity-filter').selectOption('');
 for(const [name,width,height] of [['desktop',1920,1080],['laptop',1366,900],['tablet',768,1024],['mobile',390,844]]){
   await page.setViewportSize({width,height});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,`document overflow at ${name}`);
   const wrong=await page.evaluate(()=>[...document.querySelectorAll('button,input,select,.panel,.risk-card,dialog,.sidebar,.tag')].filter(node=>getComputedStyle(node).borderRadius!=='0px').length);
   assert.equal(wrong,0,`non-square controls at ${name}`);
   await page.evaluate(()=>{document.activeElement.blur();window.scrollTo(0,0)});
   await page.waitForFunction(()=>Number(document.querySelector('.gauge text').textContent)===67);
   await page.screenshot({path:path.join(output,`analysis-${name}.png`),fullPage:true});
 }
 await page.getByRole('link',{name:'Document history'}).click();
 await page.getByRole('button',{name:/risk-fixture.pdf/}).first().waitFor();
 await page.getByRole('button',{name:/risk-fixture.pdf/}).first().click();
 await page.locator('#analysis-title').filter({hasText:'risk-fixture.pdf'}).waitFor();
 await page.getByRole('link',{name:'New analysis'}).click();
 await page.locator('#file-input').setInputFiles({name:'<img src=x onerror=window.pwned=1>.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(fixture)});
 await page.getByRole('button',{name:'Analyze agreement'}).click();
 await page.locator('#analysis-title').filter({hasText:'<img src=x onerror=window.pwned=1>.pdf'}).waitFor();
 assert.equal(await page.evaluate(()=>window.pwned),undefined);
 assert.equal(await page.locator('#analysis-title img').count(),0);
 await page.getByRole('link',{name:'Document history'}).click();
 await page.getByRole('button',{name:'Delete analysis of <img src=x onerror=window.pwned=1>.pdf'}).click();
 await page.getByRole('button',{name:'Delete analysis',exact:true}).click();
 await page.locator('#notice').filter({hasText:'Analysis deleted'}).waitFor();
 await page.getByRole('button',{name:'Delete analysis of risk-fixture.pdf'}).click();
 await page.getByRole('button',{name:'Delete analysis',exact:true}).click();
 await page.getByText('Your document register is empty',{exact:true}).waitFor();
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify({passed:true,viewports:[1920,1366,768,390],checks:['empty-state','upload','rule-mode','evidence-expansion','search','severity-filter','history-reload','square-controls','responsive-no-overflow','filename-XSS-protection','deletion'],pageErrors:errors},null,2));
 console.log('PASS browser: upload, evidence/search/filter, history, deletion, safe filename rendering; 4 responsive sizes, square controls, no page errors');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
