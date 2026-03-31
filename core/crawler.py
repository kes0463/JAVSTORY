import time
import os
import json
import re
import sys
from curl_cffi import requests
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

# 새로운 바이패스 매니저 임포트
try:
    from core import bypass_manager
except ImportError:
    import bypass_manager

class GrokWebCrawler:
    """사용자 요청: OpenRouter의 xAI Grok 모델을 활용한 실시간 웹 검색 및 무검열 크롤링"""
    def __init__(self, api_key):
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = "x-ai/grok-4-fast" 
        
    def fetch_metadata(self, product_code, html_context=None):
        if not html_context:
            return None
            
        print(f"[Grok API] 메타데이터 분석 중... 품번: {product_code}")
        # 컨텍스트를 충분히 제공 (Grok-4-fast는 컨텍스트 윈도우가 큼)
        context_str = f"\n[참고 HTML 데이터]\n{html_context[:8000]}"
        
        system_prompt = f"""
        너는 JAV 메타데이터 정제 전문가다. 제공된 사이트 데이터나 지식을 바탕으로 정확한 정보를 추출한다.
        {context_str}
        
        [추출 데이터]
        - 이 영상의 공식 일본어 및 한국어 원본 제목
        - 출연 여배우들의 정확한 이름
        - 장르 태그 (콤마로 구분)
        - 해상도가 높은 표지(Cover Image)의 직접 링크(URL)
        - 짧은 공식 시놉시스
        
        결과는 오직 아래의 정확한 JSON 포맷으로만 출력하며, 마크다운 등 기타 텍스트는 금지한다.
        {{
            "title": "타이틀",
            "actors": "배우명",
            "genres": "장르",
            "cover_url": "https://...",
            "synopsis": "시놉시스"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"품번 {product_code}의 정보를 JSON으로 추출해줘."}
                ],
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            if "```json" in result_text:
                result_text = re.search(r'```json\n?(.*?)\n?```', result_text, re.DOTALL).group(1)
            
            return json.loads(result_text)
        except Exception as e:
            print(f"[Grok API] 분석 에러: {e}")
            return None

class SecureJavCrawler:
    """BypassManager(GoodbyeDPI) + DrissionPage 통합 크롤러"""
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        self.cookies = {'over18': '1'}
        # 바이패스 매니저 시작 (이미 실행 중이면 무시됨)
        try:
            bypass_manager.manager.start()
        except NameError:
            pass

    def get_html_fast(self, url):
        """curl-cffi를 이용한 빠른 요청 (Fingerprint 우회 가능)"""
        try:
            resp = requests.get(url, headers=self.headers, cookies=self.cookies, impersonate="chrome120", timeout=10)
            if resp.status_code == 200:
                if "Just a moment..." in resp.text:
                    print("[Secure] Cloudflare 탐지됨. DrissionPage로 전환합니다...")
                    return None
                return resp.text
            return None
        except Exception as e:
            print(f"[Secure] 빠른 요청 실패 (10054 등): {e}")
            return None

    def get_html_robust(self, url):
        """DrissionPage (브라우저 제어)를 이용한 강력한 우회 요청"""
        print(f"[Robust] DrissionPage로 접속 중: {url}")
        # headless 모드로 실행 (창을 안 띄움)
        co = ChromiumOptions().set_argument('--no-sandbox').headless()
        page = ChromiumPage(co)
        try:
            page.get(url)
            
            # 클라우드플레어 통과 대기
            if "Just a moment..." in page.html:
                print("[Robust] Cloudflare 통과 대기 중 (5초)...")
                time.sleep(5)
            
            # 성인 인증 버튼 클릭 (javdb 대응)
            for selector in ['text:18歳以上', '.over18-button', 'button[primary]']:
                btn = page.ele(selector, timeout=2)
                if btn:
                    print(f"[Robust] 성인 인증 버튼({selector})을 클릭합니다.")
                    btn.click()
                    time.sleep(1)
                    break
            
            return page.html
        except Exception as e:
            print(f"[Robust] 실패: {e}")
            return None
        finally:
            page.quit()

    def search_javdb(self, product_code):
        search_url = f"https://javdb.com/search?q={product_code}&f=all"
        
        # 1. 먼저 빠른 방식으로 시도
        html = self.get_html_fast(search_url)
        
        # 2. 실패 시(차단 등) 브라우저 방식으로 재시도
        if not html:
            html = self.get_html_robust(search_url)
            
        if not html: return None
        
        soup = BeautifulSoup(html, 'html.parser')
        item = soup.select_one(".grid-item a")
        if item:
            detail_url = "https://javdb.com" + item['href']
            res = self.get_html_fast(detail_url)
            return res if res else self.get_html_robust(detail_url)
        return None

    def download_image(self, url, save_path):
        try:
            headers = self.headers.copy()
            headers['Referer'] = 'https://javdb.com/'
            r = requests.get(url, headers=headers, impersonate="chrome120", stream=True)
            if r.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                return True
        except Exception:
            return False
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY") 
    
    code = "STAR-471"
    secure = SecureJavCrawler()
    
    print(f"--- {code} 테스트 시작 ---")
    html = secure.search_javdb(code)
    if html:
        print(f"[성공] HTML 획득 성공 (길이: {len(html)})")
    else:
        print("[실패] 데이터를 가져오지 못했습니다.")
    
    # 테스트 종료 시 GoodbyeDPI 수동 종료 (실제 앱에서는 main.py에서 관리)
    try:
        bypass_manager.manager.stop()
    except NameError:
        pass
