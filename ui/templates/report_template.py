from jinja2 import Template

# [Phase 4] 장면 분석 통합 인터랙티브 웹 리포트 템플릿
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - 장면 분석 리포트</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-color: #38bdf8;
            --text-primary: #f8fafc;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            margin: 0; padding: 20px;
        }
        .header { text-align: center; margin-bottom: 40px; }
        .scene-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .scene-card {
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.3s ease, z-index 0.3s;
            cursor: pointer;
            position: relative;
        }
        .scene-card:hover {
            transform: scale(1.1);
            z-index: 50;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .img-container {
            width: 100%;
            aspect-ratio: 16 / 9;
            background: #000;
        }
        .img-container img {
            width: 100%; height: 100%;
            object-fit: cover;
        }
        .scene-info { padding: 15px; }
        .scene-time {
            font-size: 0.8rem;
            color: var(--accent-color);
            margin-bottom: 8px;
        }
        .scene-summary {
            font-size: 0.95rem;
            line-height: 1.5;
        }
        /* [Click-to-Seek] 기능을 위한 비디오 플레이어 */
        #video-player-container {
            position: sticky; top: 20px;
            margin-bottom: 30px;
            width: 100%; max-width: 800px;
            margin-left: auto; margin-right: auto;
            z-index: 100;
        }
        video { width: 100%; border-radius: 12px; border: 2px solid var(--accent-color); }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }} ({{ product_code }})</h1>
        <p>인터랙티브 분석 스토리보드</p>
    </div>

    <div id="video-player-container">
        <video id="main-player" controls>
            <source src="{{ video_path }}" type="video/mp4">
        </video>
    </div>

    <div class="scene-container">
        {% for scene in scenes %}
        <div class="scene-card" onclick="seekVideo({{ scene.start_time }})">
            <div class="img-container">
                <img src="{{ scene.image_rel_path }}" alt="Scene {{ scene.id }}" loading="lazy">
            </div>
            <div class="scene-info">
                <div class="scene-time">{{ scene.start_time | format_duration }} ~ {{ scene.end_time | format_duration }}</div>
                <div class="scene-summary">{{ scene.summary or "장면 분석 대기 중..." }}</div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        const player = document.getElementById('main-player');
        function seekVideo(seconds) {
            player.currentTime = seconds;
            player.play();
            player.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    </script>
</body>
</html>
"""

def generate_html_report(data: dict) -> str:
    """데이터를 받아 Jinja2 템플릿으로 리포트 생성"""
    
    def format_duration(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

    template = Template(REPORT_TEMPLATE)
    template.globals['format_duration'] = format_duration
    return template.render(**data)
