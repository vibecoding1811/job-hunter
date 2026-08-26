import os
from flask import Flask, render_template, request, jsonify
import models
import config
from scraper import scrape_all_companies

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'job-hunter-key-2025')

def init_app():
    models.init_db()
    for company in config.TARGET_COMPANIES:
        models.add_company(company['name'], company['group'], company['url'], company['excluded'])
    for name in config.EXCLUDED_COMPANIES:
        models.add_company(name, "平安集团", "", True)
    print("✅ 初始化完成")

init_app()

@app.route('/')
def index():
    return render_template('index.html', stats=models.get_stats())

@app.route('/api/jobs')
def api_get_jobs():
    status = request.args.get('status', '')
    jobs = models.get_jobs_by_status(status) if status else models.get_all_jobs_with_status()
    return jsonify(jobs)

@app.route('/api/jobs/<int:job_id>/status', methods=['POST'])
def api_update_status(job_id):
    data = request.json
    models.update_job_status(job_id, data.get('status', 'unread'), data.get('notes', ''))
    return jsonify({'success': True})

@app.route('/api/jobs', methods=['POST'])
def api_add_job():
    data = request.json
    company_id = data.get('company_id')
    if not company_id:
        companies = models.get_active_companies()
        for c in companies:
            if c['name'] == data.get('company_name'):
                company_id = c['id']
                break
        if not company_id:
            models.add_company(data.get('company_name', '未知公司'), '其他', '')
            companies = models.get_active_companies()
            for c in companies:
                if c['name'] == data.get('company_name'):
                    company_id = c['id']
                    break
    if not company_id:
        return jsonify({'success': False, 'error': '公司不存在'}), 400
    job_id = models.add_job(
        company_id=company_id, title=data.get('title',''),
        summary=data.get('summary',''), salary_min=data.get('salary_min'),
        salary_max=data.get('salary_max'), salary_text=data.get('salary_text',''),
        location=data.get('location',''), work_type=data.get('work_type','onsite'),
        source=data.get('source','手动添加'), url=data.get('url',''),
        keywords=data.get('keywords',''))
    return jsonify({'success': True, 'job_id': job_id})

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def api_delete_job(job_id):
    models.delete_job(job_id)
    return jsonify({'success': True})

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    try:
        count = scrape_all_companies()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    return jsonify(models.get_stats())

@app.route('/api/companies')
def api_companies():
    return jsonify(models.get_active_companies())

@app.route('/api/search', methods=['GET'])
def api_search():
    return jsonify(models.search_jobs(
        request.args.get('keyword',''), request.args.get('location',''),
        request.args.get('salary_min', type=float), request.args.get('salary_max', type=float)))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
