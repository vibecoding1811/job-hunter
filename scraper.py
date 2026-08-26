import requests
from bs4 import BeautifulSoup
import re, time, random
from datetime import datetime
import models
from config import SEARCH_KEYWORDS, PREFERRED_LOCATIONS, SALARY_MIN, SALARY_MAX

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

def safe_request(url, timeout=20):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.encoding = 'utf-8'
        return resp
    except Exception as e:
        print(f"  ❌ 请求失败: {str(e)}")
        return None

def extract_salary(text):
    if not text: return None, None, text
    patterns = [
        (r'(\d+\.?\d*)\s*[Kk]\s*[-~至到]\s*(\d+\.?\d*)\s*[Kk]', False),
        (r'(\d+\.?\d*)\s*万\s*[-~至到]\s*(\d+\.?\d*)\s*万', True),
        (r'(\d+\.?\d*)\s*[kK]\s*', False),
        (r'(\d+\.?\d*)\s*万\s*', True),
        (r'(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*[kK]', False),
        (r'(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*万', True),
    ]
    for pattern, is_wan in patterns:
        m = re.search(pattern, text)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                return (float(groups[0]), float(groups[1]), text) if is_wan else (round(float(groups[0])/10,1), round(float(groups[1])/10,1), text)
            elif len(groups) == 1:
                return (float(groups[0]), float(groups[0]), text) if is_wan else (round(float(groups[0])/10,1), round(float(groups[0])/10,1), text)
    return None, None, text

def extract_location(text):
    if not text: return ""
    cities = ["深圳", "香港", "广州", "北京", "上海", "杭州", "成都", "武汉", "南京", "苏州", "西安", "长沙"]
    for city in cities:
        if city in text:
            return city
    return text[:20] if text else ""

def match_keywords(text):
    text = text.lower()
    matched = []
    for kw in SEARCH_KEYWORDS:
        if kw.lower() in text:
            matched.append(kw)
    if not matched:
        broad = ['财务', '战略', '数字', '科技', '咨询', '总监', '经理', '总裁', '副总',
                 '官', '产品', '运营', '管理', 'cfo', '首席', 'vp', '数字化', '转型']
        for b in broad:
            if b.lower() in text:
                matched.append(b)
                break
    return matched

# ========== 猎聘搜索（全部关键词+全部城市+公司名） ==========
def scrape_liepin():
    """搜索猎聘网 - 全范围"""
    print("\n🔍 猎聘网搜索中...")
    jobs = []
    base_url = "https://www.liepin.com/zhaopin/"
    
    # 搜索所有关键词 × 所有城市
    total_searches = len(SEARCH_KEYWORDS) * len(PREFERRED_LOCATIONS)
    count = 0
    
    for keyword in SEARCH_KEYWORDS:
        for city in PREFERRED_LOCATIONS:
            count += 1
            url = f"{base_url}?key={keyword}&dqs={city}"
            print(f"  [{count}/{total_searches}] {keyword} - {city}")
            
            resp = safe_request(url)
            if not resp:
                time.sleep(random.uniform(1, 2))
                continue
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = (soup.find_all('div', class_=re.compile(r'job-card|job-item|sojob-item', re.I)) or
                     soup.find_all('li', class_=re.compile(r'job-item|position', re.I)) or
                     soup.find_all('div', attrs={'data-job-id': True}))
            
            for item in items[:8]:
                try:
                    title_el = (item.find(['h3','a','span'], class_=re.compile(r'title|name|job-name', re.I)) or
                               item.find('a', href=re.compile(r'job|position', re.I)))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 4: continue
                    
                    link = title_el if title_el.name=='a' and title_el.get('href') else item.find('a', href=True)
                    job_url = ""
                    if link and link.get('href'):
                        job_url = link['href']
                        if not job_url.startswith('http'):
                            job_url = f"https://www.liepin.com{job_url}"
                    
                    text = item.get_text(separator=' ', strip=True)
                    matched = match_keywords(f"{title} {text}")
                    if not matched: continue
                    
                    salary_el = item.find(class_=re.compile(r'salary|pay|money', re.I))
                    salary_text = salary_el.get_text(strip=True) if salary_el else ""
                    loc_el = item.find(class_=re.compile(r'loc|city|area|address', re.I))
                    location = extract_location(loc_el.get_text(strip=True)) if loc_el else city
                    smin, smax, _ = extract_salary(salary_text)
                    company_el = item.find(class_=re.compile(r'company|crop', re.I))
                    company_name = company_el.get_text(strip=True) if company_el else ""
                    
                    # 避免重复
                    is_dup = False
                    for j in jobs:
                        if j['title'] == title[:100] and j['company_name'] == company_name:
                            is_dup = True
                            break
                    if is_dup: continue
                    
                    jobs.append({
                        'title': title[:100], 'summary': text[:300],
                        'salary_min': smin, 'salary_max': smax, 'salary_text': salary_text[:50],
                        'location': location, 'url': job_url, 'keywords': ','.join(matched),
                        'source': '猎聘', 'company_name': company_name,
                    })
                except: continue
            
            time.sleep(random.uniform(1.5, 3))
    
    print(f"  ✅ 猎聘: {len(jobs)} 个岗位")
    return jobs

# ========== LinkedIn搜索 ==========
def scrape_linkedin():
    """搜索LinkedIn"""
    print("\n🔍 LinkedIn搜索中...")
    jobs = []
    base_url = "https://www.linkedin.com/jobs/search/"
    
    keywords_sample = SEARCH_KEYWORDS[:8]
    cities_sample = PREFERRED_LOCATIONS[:4]
    
    for keyword in keywords_sample:
        for city in cities_sample:
            url = f"{base_url}?keywords={keyword}&location={city}"
            print(f"  搜索: {keyword} - {city}")
            
            resp = safe_request(url)
            if not resp: continue
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = (soup.find_all('li', class_=re.compile(r'job-card|result-card', re.I)) or
                    soup.find_all('div', class_=re.compile(r'job-search-card|base-card', re.I)))
            
            for item in items[:8]:
                try:
                    title_el = item.find(['h3','a','span'], class_=re.compile(r'title|job-title', re.I))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if not title: continue
                    
                    link = item.find('a', href=re.compile(r'jobs/view', re.I))
                    job_url = link['href'] if link and link.get('href') else ""
                    if job_url and not job_url.startswith('http'):
                        job_url = f"https://www.linkedin.com{job_url}"
                    
                    text = item.get_text(separator=' ', strip=True)
                    matched = match_keywords(f"{title} {text}")
                    if not matched: continue
                    
                    loc_el = item.find(class_=re.compile(r'location|loc', re.I))
                    location = extract_location(loc_el.get_text(strip=True)) if loc_el else city
                    company_el = item.find(class_=re.compile(r'company|org', re.I))
                    company_name = company_el.get_text(strip=True) if company_el else ""
                    
                    is_dup = False
                    for j in jobs:
                        if j['title'] == title[:100] and j['company_name'] == company_name:
                            is_dup = True; break
                    if is_dup: continue
                    
                    jobs.append({
                        'title': title[:100], 'summary': text[:300],
                        'salary_min': None, 'salary_max': None, 'salary_text': '',
                        'location': location, 'url': job_url, 'keywords': ','.join(matched),
                        'source': 'LinkedIn', 'company_name': company_name,
                    })
                except: continue
            time.sleep(random.uniform(2, 3))
    
    print(f"  ✅ LinkedIn: {len(jobs)} 个岗位")
    return jobs

# ========== 公司官网搜索 ==========
def scrape_company_website(company):
    print(f"  📁 官网: {company['name']}")
    jobs = []
    if not company['careers_url']: return jobs
    
    resp = safe_request(company['careers_url'])
    if not resp: return jobs
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for tag in soup(['script','style','nav','footer','header']): tag.decompose()
    
    links = soup.find_all('a', href=True)
    for link in links:
        try:
            href = link['href']
            link_text = link.get_text(strip=True)
            if not link_text or len(link_text) < 4: continue
            
            matched = match_keywords(link_text)
            if not matched: continue
            
            job_url = href
            if not job_url.startswith('http'):
                from urllib.parse import urljoin
                job_url = urljoin(company['careers_url'], job_url)
            
            # 去重
            is_dup = False
            for j in jobs:
                if j['title'] == link_text[:100]: is_dup = True; break
            if is_dup: continue
            
            jobs.append({
                'title': link_text[:100], 'summary': '',
                'salary_min': None, 'salary_max': None, 'salary_text': '',
                'location': '', 'url': job_url, 'keywords': ','.join(matched),
                'source': '官网', 'company_name': company['name'],
            })
        except: continue
    
    print(f"    → {len(jobs)} 个匹配")
    return jobs

# ========== 存入数据库 ==========
def save_jobs_to_db(jobs, source_name):
    """将岗位存入数据库"""
    companies = {c['name']: c for c in models.get_active_companies()}
    
    # 确保有平台公司
    platform_name = source_name
    if platform_name not in companies:
        models.add_company(platform_name, '招聘平台', '')
        companies = {c['name']: c for c in models.get_active_companies()}
    
    platform_id = companies.get(platform_name, {}).get('id')
    count = 0
    
    for job_data in jobs:
        company_name = job_data.get('company_name', '')
        company_id = None
        
        # 尝试匹配已知公司
        if company_name:
            if company_name in companies:
                company_id = companies[company_name]['id']
            else:
                for c_name, c_info in companies.items():
                    if c_name in company_name or company_name in c_name:
                        if c_info.get('is_excluded', 0) == 0:
                            company_id = c_info['id']
                            break
        
        if not company_id:
            company_id = platform_id
        
        if company_id:
            try:
                models.add_job(
                    company_id=company_id, title=job_data['title'],
                    summary=job_data['summary'],
                    salary_min=job_data['salary_min'], salary_max=job_data['salary_max'],
                    salary_text=job_data['salary_text'], location=job_data['location'],
                    source=job_data['source'], url=job_data['url'],
                    keywords=job_data['keywords'],
                )
                count += 1
            except: continue
    
    return count

# ========== 主函数 ==========
def scrape_all_companies():
    print("=" * 60)
    print(f"🚀 开始全范围搜索... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    total = 0
    
    # 1. 猎聘（全范围）
    print("\n" + "=" * 40)
    liepin_jobs = scrape_liepin()
    c1 = save_jobs_to_db(liepin_jobs, '猎聘网')
    total += c1
    print(f"📊 猎聘网存入: {c1} 个")
    
    # 2. LinkedIn
    print("\n" + "=" * 40)
    linkedin_jobs = scrape_linkedin()
    c2 = save_jobs_to_db(linkedin_jobs, 'LinkedIn')
    total += c2
    print(f"📊 LinkedIn存入: {c2} 个")
    
    # 3. 公司官网
    print("\n" + "=" * 40)
    print("📁 搜索公司官网...")
    active_companies = models.get_active_companies()
    for company in active_companies:
        if not company['careers_url']: continue
        time.sleep(random.uniform(1, 2))
        jobs = scrape_company_website(company)
        for job_data in jobs:
            try:
                models.add_job(
                    company_id=company['id'], title=job_data['title'],
                    summary=job_data['summary'],
                    salary_min=job_data['salary_min'], salary_max=job_data['salary_max'],
                    salary_text=job_data['salary_text'], location=job_data['location'],
                    source=job_data['source'], url=job_data['url'],
                    keywords=job_data['keywords'],
                )
                total += 1
            except: continue
    
    print("\n" + "=" * 60)
    print(f"✅ 搜索完成！")
    print(f"   猎聘: {len(liepin_jobs)} 个")
    print(f"   LinkedIn: {len(linkedin_jobs)} 个")
    print(f"   官网: 已补充搜索")
    print(f"   📊 共存入 {total} 个新岗位")
    print("=" * 60)
    
    return total
