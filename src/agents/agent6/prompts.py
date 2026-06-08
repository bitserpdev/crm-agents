DAILY_DIGEST_SUBJECT = "Upwork Daily Digest – {date} – {job_count} new jobs"

DAILY_DIGEST_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .stats { background: #f0fdf4; padding: 15px; text-align: center; border-bottom: 1px solid #ddd; }
        .job-card { border: 1px solid #e2e8f0; border-radius: 8px; margin: 20px 0; padding: 20px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .job-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .job-title a { color: #4f46e5; text-decoration: none; }
        .job-title a:hover { text-decoration: underline; }
        .job-meta { display: flex; gap: 15px; margin-bottom: 10px; flex-wrap: wrap; }
        .meta-badge { background: #f1f5f9; padding: 4px 10px; border-radius: 15px; font-size: 12px; }
        .budget { background: #dcfce7; color: #166534; }
        .skills { margin: 10px 0; }
        .skill-tag { background: #e2e8f0; padding: 3px 8px; border-radius: 12px; font-size: 11px; margin-right: 5px; display: inline-block; }
        .description { color: #475569; font-size: 13px; margin: 10px 0; }
        .view-link { display: inline-block; background: #4f46e5; color: white; padding: 6px 15px; border-radius: 6px; text-decoration: none; font-size: 12px; margin-top: 10px; }
        .footer { text-align: center; padding: 20px; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Upwork Daily Job Digest</h1>
        <p>Your personalized freelance opportunities for {date}</p>
    </div>
    
    <div class="stats">
        <span style="font-size: 24px; font-weight: bold;">{job_count}</span>
        <span> new jobs found matching your criteria</span>
    </div>
    
    {jobs_html}
    
    <div class="footer">
        <p>This is an automated digest from BITS CRM Agent System.</p>
        <p>To modify your filters, contact your system administrator.</p>
    </div>
</body>
</html>
"""