import requests
from bs4 import BeautifulSoup
import re, time, random
from datetime import datetime
import models
from config import SEARCH_KEYWORDS, PREFERRED_LOCATIONS, SALARY_MIN, SALARY_MAX
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}
def safe_request(url, timeout=15):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.encoding = resp.apparent_encoding
        return resp
    except:
        return None
def extract_salary(text):
    if not text: return None,None,text
    for p in [r'(\d+\.?\d*)\s*[Kk]\s*[-~至到]\s*(\d+\.?\d*)\s*[Kk]', r'(\d+\.?\d*)\s*万\s*[-~至到]\s*(\d+\.?\d*)\s*万', r'(\d+\.?\d*)\s*[kK]\s*', r'(\d+\.?\d*)\s*万\s*']:
        m = re.search(p, text)
        if m:
            g = m.groups()
            if len(g)==2:
                return (float(g[0]),float(g[1]),text) if '万' in text else (float(g[0])/10,float(g[1])/10,text)
            elif len(g)==1:
                return (float(g[0]),float(g[0]),text) if '万' in text else (float(g[0])/10,float(g[0])/10,text)
    return None,None,text
def extract_location(text):
    if not text: return ""
    for c in ["深圳","香港","广州","北京","上海","杭州","成都","武汉","南京"]:
        if c in text: return c
    return text[:10]
def scrape_generic(company_name, url):
    print(f"  爬取 {company_name}...")
    jobs = []
    resp = safe_request(url)
    if not resp: return jobs
    soup = BeautifulSoup(resp.text, 'html.parser')
    elements = []
    for p in ['job','position','career','vacancy','recruit','job-list','position-list','job-item','position-item','job-card']:
        e = soup.find_all(class_=re.compile(p, re.I))
        if e: elements = e; break
    if not elements: elements = soup.find_all('li', class_=re.compile(r'job|position|career', re.I))
    if not elements: elements = soup.find_all('a', href=re.compile(r'job|position|career', re.I))
    for elem in elements[:50]:
        try:
            title = ""
            te = elem.find(['h2','h3','h4','a','span','div'], class_=re.compile(r'title|name|position', re.I))
            if te: title = te.get_text(strip=True)
            elif elem.name=='a': title = elem.get_text(strip=True)
            if not title: continue
            job_url = ""
            if elem.name=='a' and elem.get('href'):
                job_url = elem['href']
                if not job_url.startswith('http'):
                    from urllib.parse import urljoin
                    job_url = urljoin(url, job_url)
            else:
                link = elem.find('a', href=True)
                if link:
                    job_url = link['href']
                    if not job_url.startswith('http'):
                        from urllib.parse import urljoin
                        job_url = urljoin(url, job_url)
            de = elem.find(class_=re.compile(r'desc|summary|intro|detail', re.I))
            summary = de.get_text(strip=True)[:200] if de else ""
            le = elem.find(class_=re.compile(r'loc|city|place|address', re.I))
            location = extract_location(le.get_text(strip=True)) if le else ""
            se = elem.find(class_=re.compile(r'salary|pay|compensation|money', re.I))
            salary_text = se.get_text(strip=True) if se else ""
            text = f"{title} {summary}".lower()
            matched = [kw for kw in SEARCH_KEYWORDS if kw.lower() in text]
            if not matched:
                for bk in ['财务','战略','数字','科技','咨询','总监','经理','总裁','副总','官','产品','运营','管理']:
                    if bk in text: matched.append(bk); break
            if not matched: continue
            smin, smax, _ = extract_salary(salary_text)
            jobs.append({'title':title[:100],'summary':summary[:300],'salary_min':smin,'salary_max':smax,'salary_text':salary_text[:50],'location':location,'url':job_url,'keywords':','.join(matched)})
        except: continue
    return jobs
def scrape_all_companies():
    print(f"🚀 开始搜索... {datetime.now()}")
    companies = models.get_active_companies()
    total = 0
    for company in companies:
        if not company['careers_url']: continue
        print(f"📁 {company['name']}")
        time.sleep(random.uniform(1,2))
        jobs = scrape_generic(company['name'], company['careers_url'])
        if not jobs: print("  ⚠️ 无匹配"); continue
        print(f"  ✅ {len(jobs)}个")
        for j in jobs:
            try:
                models.add_job(company_id=company['id'], title=j['title'], summary=j['summary'], salary_min=j['salary_min'], salary_max=j['salary_max'], salary_text=j['salary_text'], location=j['location'], source="官网", url=j['url'], keywords=j['keywords'])
                total += 1
            except: continue
    print(f"✅ 完成！共{total}个新岗位")
    return total
